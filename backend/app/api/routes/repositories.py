import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_repository
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    IN_PROGRESS_STATUSES,
    AnalysisFile,
    AnalysisStatus,
    RepositoryAnalysis,
    SavedRepository,
    User,
)
from app.schemas.repository import (
    ImportantFile,
    RepositoryCreate,
    RepositoryDetail,
    RepositorySummary,
)
from app.services import repositories
from app.services.analysis.importance import IMPORTANT_THRESHOLD
from app.services.ingestion.errors import InvalidRepositoryUrl
from app.services.ingestion.github_url import parse_github_url
from app.services.ingestion.pipeline import run_github_analysis
from app.worker.runner import JobRunner, get_job_runner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/repositories", tags=["repositories"])

MAX_IMPORTANT_FILES = 12


def _start_analysis(
    db: Session, user: User, repository: SavedRepository, runner: JobRunner
) -> RepositoryAnalysis:
    """Queue a new analysis and hand it to the background runner."""
    limit = get_settings().max_active_analyses_per_user
    if repositories.active_analysis_count(db, user.id) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You already have {limit} analyses running. Wait for one to finish.",
        )
    analysis = repositories.create_analysis(db, repository)
    runner.submit(run_github_analysis, analysis.id)
    db.refresh(analysis)  # an inline runner may already have finished it
    return analysis


def _is_in_progress(analysis: RepositoryAnalysis | None) -> bool:
    return analysis is not None and analysis.status in IN_PROGRESS_STATUSES


def _base(repository: SavedRepository) -> dict:
    return {
        "id": repository.id,
        "source_type": repository.source_type,
        "source_url": repository.source_url,
        "owner": repository.owner,
        "name": repository.name,
        "label": repository.label,
        "created_at": repository.created_at,
    }


def _important_files(db: Session, analysis: RepositoryAnalysis) -> list[ImportantFile]:
    rows = db.scalars(
        select(AnalysisFile)
        .where(
            AnalysisFile.analysis_id == analysis.id,
            AnalysisFile.skipped_reason.is_(None),
            AnalysisFile.importance_score >= IMPORTANT_THRESHOLD,
        )
        .order_by(AnalysisFile.importance_score.desc(), AnalysisFile.path)
        .limit(MAX_IMPORTANT_FILES)
    )
    return [
        ImportantFile(
            path=f.path,
            language=f.language,
            score=f.importance_score,
            reasons=f.importance_reasons or [],
        )
        for f in rows
    ]


def _detail(
    db: Session, repository: SavedRepository, analysis: RepositoryAnalysis | None
) -> RepositoryDetail:
    completed = analysis is not None and analysis.status == AnalysisStatus.COMPLETED
    return RepositoryDetail.model_validate(
        {
            **_base(repository),
            "latest_analysis": analysis,
            "important_files": _important_files(db, analysis) if completed else [],
        },
        from_attributes=True,
    )


@router.post("", response_model=RepositoryDetail, status_code=status.HTTP_202_ACCEPTED)
def add_repository(
    body: RepositoryCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> RepositoryDetail:
    """Save a public GitHub repository to the library and start analyzing it.

    Adding one that is already saved returns the existing entry (200) instead of
    creating a duplicate. It only starts a new analysis if the last one failed.
    """
    try:
        ref = parse_github_url(body.url)
    except InvalidRepositoryUrl as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error.message) from None

    repository = repositories.get_or_create_github(db, user.id, ref)
    analysis = repositories.latest_analysis(db, repository.id)

    if analysis is not None and analysis.status != AnalysisStatus.FAILED:
        response.status_code = status.HTTP_200_OK
    else:
        analysis = _start_analysis(db, user, repository, runner)
    return _detail(db, repository, analysis)


@router.get("", response_model=list[RepositorySummary])
def list_repositories(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[RepositorySummary]:
    saved = repositories.list_for_user(db, user.id)
    latest = repositories.latest_analyses(db, [r.id for r in saved])
    summaries = []
    for repository in saved:
        analysis = latest.get(repository.id)
        description = (analysis.github_metadata or {}).get("description") if analysis else None
        summaries.append(
            RepositorySummary.model_validate(
                {**_base(repository), "description": description, "latest_analysis": analysis},
                from_attributes=True,
            )
        )
    return summaries


@router.get("/{repository_id}", response_model=RepositoryDetail)
def get_repository(
    repository: SavedRepository = Depends(get_owned_repository), db: Session = Depends(get_db)
) -> RepositoryDetail:
    return _detail(db, repository, repositories.latest_analysis(db, repository.id))


@router.post(
    "/{repository_id}/analyses",
    response_model=RepositoryDetail,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_new_analysis(
    repository: SavedRepository = Depends(get_owned_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> RepositoryDetail:
    """Analyze the repository again (used to retry a failure, and later to refresh)."""
    if _is_in_progress(repositories.latest_analysis(db, repository.id)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="This repository is already being analyzed"
        )
    analysis = _start_analysis(db, user, repository, runner)
    return _detail(db, repository, analysis)

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
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
    AnalysisSummary,
    ChangesOut,
    ImportantFile,
    RepositoryCreate,
    RepositoryDetail,
    RepositorySummary,
    RepositoryUpdate,
    VersionChanges,
)
from app.services import library, repositories
from app.services.analysis.importance import IMPORTANT_THRESHOLD
from app.services.ingestion.errors import InvalidRepositoryUrl
from app.services.ingestion.github_url import parse_github_url
from app.services.ingestion.pipeline import run_analysis
from app.storage import artifacts
from app.worker.runner import JobRunner, get_job_runner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/repositories", tags=["repositories"])

MAX_IMPORTANT_FILES = 12
# A ZIP file starts with a local file header, or (if empty) the end-of-archive record.
ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06")


def _start_analysis(
    db: Session, user: User, repository: SavedRepository, runner: JobRunner
) -> RepositoryAnalysis:
    """Queue a new analysis and hand it to the background runner."""
    _check_analysis_limit(db, user)
    analysis = repositories.create_analysis(db, repository)
    runner.submit(run_analysis, analysis.id)
    db.expire_all()  # an inline runner may already have finished it, in its own session
    return analysis


def _check_analysis_limit(db: Session, user: User) -> None:
    limit = get_settings().max_active_analyses_per_user
    if repositories.active_analysis_count(db, user.id) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You already have {limit} analyses running. Wait for one to finish.",
        )


def _is_in_progress(analysis: RepositoryAnalysis | None) -> bool:
    return analysis is not None and analysis.status in IN_PROGRESS_STATUSES


def _base(repository: SavedRepository, collection_ids: list[uuid.UUID]) -> dict:
    return {
        "id": repository.id,
        "source_type": repository.source_type,
        "source_url": repository.source_url,
        "owner": repository.owner,
        "name": repository.name,
        "labels": repository.labels or [],
        "collection_ids": collection_ids,
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


def _detail(db: Session, repository: SavedRepository) -> RepositoryDetail:
    latest = repositories.latest_analysis(db, repository.id)
    current = library.latest_completed(db, repository.id)
    return RepositoryDetail.model_validate(
        {
            **_base(repository, library.collection_ids(db, [repository.id])[repository.id]),
            "latest_analysis": latest,
            "current_analysis": current,
            "important_files": _important_files(db, current) if current else [],
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
        _start_analysis(db, user, repository, runner)
    return _detail(db, repository)


def _languages(
    analysis: RepositoryAnalysis | None, limit: int = 3
) -> tuple[list[dict], int | None]:
    """The main programming languages by lines of code, and the total lines."""
    stats = (analysis.code_stats or {}) if analysis else {}
    rows = [r for r in stats.get("languages", []) if r.get("is_programming") and r.get("lines")]
    total = sum(r["lines"] for r in rows)
    if not total:
        return [], None
    rows.sort(key=lambda r: r["lines"], reverse=True)
    shares = [{"name": r["name"], "share": round(r["lines"] / total, 3)} for r in rows[:limit]]
    return shares, stats.get("totals", {}).get("code_lines", total)


@router.get("", response_model=list[RepositorySummary])
def list_repositories(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[RepositorySummary]:
    saved = repositories.list_for_user(db, user.id)
    ids = [r.id for r in saved]
    latest = repositories.latest_analyses(db, ids)
    memberships = library.collection_ids(db, ids)
    summaries = []
    for repository in saved:
        analysis = latest.get(repository.id)
        description = (analysis.github_metadata or {}).get("description") if analysis else None
        languages, code_lines = _languages(analysis)
        summaries.append(
            RepositorySummary.model_validate(
                {
                    **_base(repository, memberships[repository.id]),
                    "description": description,
                    "latest_analysis": analysis,
                    "languages": languages,
                    "code_lines": code_lines,
                },
                from_attributes=True,
            )
        )
    return summaries


@router.get("/{repository_id}", response_model=RepositoryDetail)
def get_repository(
    repository: SavedRepository = Depends(get_owned_repository), db: Session = Depends(get_db)
) -> RepositoryDetail:
    return _detail(db, repository)


@router.patch("/{repository_id}", response_model=RepositoryDetail)
def update_repository(
    body: RepositoryUpdate,
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> RepositoryDetail:
    """Replace the repository's labels."""
    try:
        repository.labels = library.normalize_labels(body.labels)
    except library.InvalidLabels as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    db.commit()
    return _detail(db, repository)


@router.delete("/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(
    repository: SavedRepository = Depends(get_owned_repository), db: Session = Depends(get_db)
) -> Response:
    """Remove the repository and everything stored for it."""
    if library.is_busy(db, repository.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This repository is being analyzed. Delete it once the analysis has finished.",
        )
    library.delete_repository(db, repository)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    """Analyze the repository again: retry a failure, or refresh to the latest commit."""
    if repository.source_type == "zip":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This project was uploaded as a ZIP file. Upload a new ZIP to refresh it.",
        )
    if _is_in_progress(repositories.latest_analysis(db, repository.id)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="This repository is already being analyzed"
        )
    _start_analysis(db, user, repository, runner)
    return _detail(db, repository)


# --- refresh history -------------------------------------------------------------------------


@router.get("/{repository_id}/analyses", response_model=list[AnalysisSummary])
def list_versions(
    repository: SavedRepository = Depends(get_owned_repository), db: Session = Depends(get_db)
) -> list[RepositoryAnalysis]:
    """Every analysis of this repository, newest first."""
    return library.history(db, repository.id)


@router.get("/{repository_id}/analyses/{analysis_id}/changes", response_model=VersionChanges)
def version_changes(
    analysis_id: uuid.UUID,
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> VersionChanges:
    """What changed in this version compared with the previous completed one."""
    analysis = db.get(RepositoryAnalysis, analysis_id)
    if analysis is None or analysis.saved_repository_id != repository.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Version not found")
    if analysis.status != AnalysisStatus.COMPLETED:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This version did not finish")
    previous = library.previous_completed(db, analysis)
    if previous is None:
        return VersionChanges(
            version=analysis.version, previous_version=None, previous_commit_sha=None, changes=None
        )
    changes = library.compare(db, previous, analysis)
    return VersionChanges(
        version=analysis.version,
        previous_version=previous.version,
        previous_commit_sha=previous.commit_sha,
        changes=ChangesOut.model_validate(changes, from_attributes=True),
    )


# --- ZIP upload ------------------------------------------------------------------------------


async def _receive_zip(request: Request) -> Path:
    """Stream the request body (the raw .zip) to a temporary file, enforcing the size limit.

    The body is read in chunks and written as it arrives, so an oversized upload is
    stopped at the limit instead of being buffered in memory or on disk first.
    """
    limit = get_settings().max_upload_bytes
    too_large = HTTPException(
        status.HTTP_413_CONTENT_TOO_LARGE,
        detail=f"The file is larger than the {limit // (1024 * 1024)} MB upload limit.",
    )
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise too_large

    incoming = artifacts.upload_dir() / f"incoming-{uuid.uuid4()}.zip"
    incoming.parent.mkdir(parents=True, exist_ok=True)
    size, start = 0, b""
    try:
        with incoming.open("wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise too_large
                if len(start) < 4:
                    start += chunk[: 4 - len(start)]
                out.write(chunk)
        if not start.startswith(ZIP_SIGNATURES):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The file is not a ZIP archive."
            )
    except BaseException:
        incoming.unlink(missing_ok=True)
        raise
    return incoming


def _queue_upload(
    db: Session,
    user: User,
    repository: SavedRepository,
    incoming: Path,
    runner: JobRunner,
) -> RepositoryDetail:
    try:
        _check_analysis_limit(db, user)
        analysis = repositories.create_analysis(db, repository)
        os.replace(incoming, artifacts.upload_path(analysis.id))
    finally:
        incoming.unlink(missing_ok=True)
    runner.submit(run_analysis, analysis.id)
    db.expire_all()  # see _start_analysis
    return _detail(db, repository)


def _upload_name(name: str) -> str:
    cleaned = " ".join(name.split())
    for suffix in (".zip", ".ZIP"):
        cleaned = cleaned.removesuffix(suffix)
    return cleaned[:200] or "Uploaded project"


@router.post("/upload", response_model=RepositoryDetail, status_code=status.HTTP_202_ACCEPTED)
async def upload_repository(
    request: Request,
    name: str = Query(min_length=1, max_length=255, description="Shown in the library"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> RepositoryDetail:
    """Add a project from a .zip file sent as the request body (Content-Type: application/zip)."""
    incoming = await _receive_zip(request)

    def create() -> RepositoryDetail:
        try:
            _check_analysis_limit(db, user)
        except HTTPException:
            incoming.unlink(missing_ok=True)
            raise
        repository = repositories.create_upload(db, user.id, _upload_name(name))
        return _queue_upload(db, user, repository, incoming, runner)

    return await run_in_threadpool(create)


@router.post(
    "/{repository_id}/upload",
    response_model=RepositoryDetail,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_new_version(
    request: Request,
    repository: SavedRepository = Depends(get_owned_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> RepositoryDetail:
    """Refresh an uploaded project with a new .zip of it."""
    if repository.source_type != "zip":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This repository comes from GitHub. Refresh it to analyze the latest commit.",
        )
    incoming = await _receive_zip(request)

    def create() -> RepositoryDetail:
        if library.is_busy(db, repository.id):
            incoming.unlink(missing_ok=True)
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="This repository is already being analyzed"
            )
        return _queue_upload(db, user, repository, incoming, runner)

    return await run_in_threadpool(create)

"""AI explanations: request one, then poll for it."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_completed_analysis, get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    AiExplanation,
    AiKind,
    AiRequest,
    AiStatus,
    AnalysisFile,
    RepositoryAnalysis,
    SavedRepository,
    User,
)
from app.schemas.ai import ExplanationOut
from app.services.ai.jobs import run_ai_job
from app.worker.runner import JobRunner, get_job_runner

router = APIRouter(prefix="/repositories/{repository_id}/ai", tags=["ai"])

Kind = Literal["overview", "technologies", "file"]


def _target(kind: str, path: str | None, analysis: RepositoryAnalysis, db: Session) -> str:
    """The path this explanation is about ("" for whole-repository kinds)."""
    if kind != AiKind.FILE:
        return ""
    if not path:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A file path is required")
    stored = db.scalar(
        select(AnalysisFile.id).where(
            AnalysisFile.analysis_id == analysis.id,
            AnalysisFile.path == path,
            AnalysisFile.skipped_reason.is_(None),
        )
    )
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")
    return path


def _out(kind: str, path: str, record: AiExplanation | None) -> ExplanationOut:
    if record is None:
        return ExplanationOut(kind=kind, path=path or None, status="missing")
    return ExplanationOut(
        id=record.id,
        kind=record.kind,
        path=record.target_path or None,
        status=record.status,
        error_code=record.error_code,
        error_message=record.error_message,
        content=record.content,
        model=record.model,
        created_at=record.created_at,
        completed_at=record.completed_at,
    )


def _find(db: Session, analysis: RepositoryAnalysis, kind: str, path: str) -> AiExplanation | None:
    return db.scalar(
        select(AiExplanation).where(
            AiExplanation.analysis_id == analysis.id,
            AiExplanation.kind == kind,
            AiExplanation.target_path == path,
        )
    )


def _user_ai_rows(user: User):
    """Counts explanations that belong to this user's repositories."""
    return (
        select(func.count())
        .select_from(AiExplanation)
        .join(RepositoryAnalysis, RepositoryAnalysis.id == AiExplanation.analysis_id)
        .join(SavedRepository, SavedRepository.id == RepositoryAnalysis.saved_repository_id)
        .where(SavedRepository.user_id == user.id)
    )


@router.get("/{kind}", response_model=ExplanationOut)
def get_explanation(
    kind: Kind,
    path: str | None = Query(default=None, max_length=1000),
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    db: Session = Depends(get_db),
) -> ExplanationOut:
    target = _target(kind, path, analysis, db)
    return _out(kind, target, _find(db, analysis, kind, target))


@router.post("/{kind}", response_model=ExplanationOut, status_code=status.HTTP_202_ACCEPTED)
def request_explanation(
    kind: Kind,
    path: str | None = Query(default=None, max_length=1000),
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> ExplanationOut:
    """Start generating an explanation, replacing an earlier one (a regenerate)."""
    settings = get_settings()
    if not settings.llm_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI explanations are not set up on this server.",
        )
    target = _target(kind, path, analysis, db)
    if kind == AiKind.TECHNOLOGIES and not analysis.technologies:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="No technologies were detected, so there is nothing to explain.",
        )

    existing = _find(db, analysis, kind, target)
    if existing is not None and existing.status == AiStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This is already being generated")

    # Free AI quotas are small, so each person gets a daily allowance and a cap on
    # simultaneous requests.
    since = datetime.now(UTC) - timedelta(days=1)
    used_today = (
        db.scalar(
            select(func.count())
            .select_from(AiRequest)
            .where(AiRequest.user_id == user.id, AiRequest.created_at >= since)
        )
        or 0
    )
    if used_today >= settings.max_ai_requests_per_user_per_day:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You have reached today's limit of {settings.max_ai_requests_per_user_per_day} "
            "AI requests. Try again tomorrow.",
        )
    running = db.scalar(_user_ai_rows(user).where(AiExplanation.status == AiStatus.PENDING)) or 0
    if running >= settings.max_active_ai_jobs_per_user:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"{running} of your AI {'request is' if running == 1 else 'requests are'} "
            "already running. Wait for one to finish.",
        )

    if existing is not None:
        db.delete(existing)
        db.flush()
    record = AiExplanation(analysis_id=analysis.id, kind=kind, target_path=target)
    db.add(record)
    db.add(AiRequest(user_id=user.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # two requests started the same explanation at once
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="This is already being generated"
        ) from None

    runner.submit(run_ai_job, record.id)
    db.refresh(record)  # an inline runner may already have finished it
    return _out(kind, target, record)

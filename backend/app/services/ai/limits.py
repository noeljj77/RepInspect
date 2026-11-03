"""The per-user AI allowance, shared by explanations, chat, interview
questions and mock interview grading.

Free model quotas are small, so each person gets a daily number of requests and a cap
on how many may run at once. Every accepted request is logged in `ai_requests`, which
only grows, so regenerating or deleting things does not give the allowance back.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AiExplanation,
    AiRequest,
    AiStatus,
    BatchStatus,
    ChatMessage,
    ChatSession,
    MessageStatus,
    MockInterview,
    MockTurn,
    QuestionBatch,
    RepositoryAnalysis,
    SavedRepository,
    TurnStatus,
    User,
)


class AiLimitReached(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _running(db: Session, user: User) -> int:
    explanations = db.scalar(
        select(func.count())
        .select_from(AiExplanation)
        .join(RepositoryAnalysis, RepositoryAnalysis.id == AiExplanation.analysis_id)
        .join(SavedRepository, SavedRepository.id == RepositoryAnalysis.saved_repository_id)
        .where(SavedRepository.user_id == user.id, AiExplanation.status == AiStatus.PENDING)
    )
    answers = db.scalar(
        select(func.count())
        .select_from(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .join(RepositoryAnalysis, RepositoryAnalysis.id == ChatSession.analysis_id)
        .join(SavedRepository, SavedRepository.id == RepositoryAnalysis.saved_repository_id)
        .where(SavedRepository.user_id == user.id, ChatMessage.status == MessageStatus.PENDING)
    )
    batches = db.scalar(
        select(func.count())
        .select_from(QuestionBatch)
        .join(SavedRepository, SavedRepository.id == QuestionBatch.saved_repository_id)
        .where(SavedRepository.user_id == user.id, QuestionBatch.status == BatchStatus.PENDING)
    )
    grading = db.scalar(
        select(func.count())
        .select_from(MockTurn)
        .join(MockInterview, MockInterview.id == MockTurn.interview_id)
        .join(SavedRepository, SavedRepository.id == MockInterview.saved_repository_id)
        .where(SavedRepository.user_id == user.id, MockTurn.status == TurnStatus.GRADING)
    )
    return (explanations or 0) + (answers or 0) + (batches or 0) + (grading or 0)


def check_allowance(db: Session, user: User) -> None:
    """Raise AiLimitReached if this person may not start another AI request now."""
    settings = get_settings()
    since = datetime.now(UTC) - timedelta(days=1)
    used_today = db.scalar(
        select(func.count())
        .select_from(AiRequest)
        .where(AiRequest.user_id == user.id, AiRequest.created_at >= since)
    )
    if (used_today or 0) >= settings.max_ai_requests_per_user_per_day:
        raise AiLimitReached(
            f"You have reached today's limit of {settings.max_ai_requests_per_user_per_day} "
            "AI requests. Try again tomorrow."
        )
    running = _running(db, user)
    if running >= settings.max_active_ai_jobs_per_user:
        raise AiLimitReached(
            f"{running} of your AI {'request is' if running == 1 else 'requests are'} "
            "already running. Wait for one to finish."
        )


def record_request(db: Session, user: User) -> None:
    """Count one accepted request. Committed together with the caller's own changes."""
    db.add(AiRequest(user_id=user.id))

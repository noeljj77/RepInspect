"""Mock interviews: a session of questions asked one at a time, graded against the code."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InterviewStatus(StrEnum):
    PREPARING = "preparing"  # choosing (and if needed writing) the questions
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class TurnStatus(StrEnum):
    WAITING = "waiting"  # asked, waiting for the answer
    GRADING = "grading"
    GRADED = "graded"
    SKIPPED = "skipped"
    FAILED = "failed"  # grading failed; it can be retried
    CANCELLED = "cancelled"  # the interview was ended before it was answered


class MockInterview(Base):
    __tablename__ = "mock_interviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    saved_repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("saved_repositories.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(12), default=InterviewStatus.PREPARING.value)
    question_count: Mapped[int]
    categories: Mapped[list | None] = mapped_column(JSONB)
    difficulty: Mapped[str | None] = mapped_column(String(20))
    # The questions to ask, in order: copies of practice questions (id, text, category,
    # difficulty, answer points). Turns are created from it one at a time, so a follow-up
    # can be asked right after its question.
    plan: Mapped[list] = mapped_column(JSONB, default=list)
    # Written when the interview ends (see services/mock/report.py).
    report: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MockTurn(Base):
    """One question (or follow-up) in a mock interview, with the answer and its grade."""

    __tablename__ = "mock_interview_turns"
    __table_args__ = (
        UniqueConstraint("interview_id", "position", name="uq_mock_interview_turns_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mock_interviews.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    kind: Mapped[str] = mapped_column(String(12))  # "question" or "follow_up"
    # The practice question it came from. Its text and answer points are copied below, so
    # grading stays the same if the practice question is edited or deleted.
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("interview_questions.id", ondelete="SET NULL")
    )
    prompt: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30))
    difficulty: Mapped[str] = mapped_column(String(20))
    # Checked findings: what a strong answer covers. A follow-up keeps its question's points
    # as background for grading.
    reference_points: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(12), default=TurnStatus.WAITING.value)
    answer: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int | None]  # 0 to 4
    # The checked grade (see services/mock/schemas.Grade).
    grade: Mapped[dict | None] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(String(80))
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(Text)
    asked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

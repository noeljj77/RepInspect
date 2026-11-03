"""Interview practice: generated questions and how far someone has got with each."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BatchStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Progress(StrEnum):
    NEW = "new"
    PRACTICING = "practicing"
    CONFIDENT = "confident"


class QuestionBatch(Base):
    """One request for questions. A background job fills it, like the AI explanations."""

    __tablename__ = "question_batches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    saved_repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("saved_repositories.id", ondelete="CASCADE"), index=True
    )
    # The version the questions were written from. Kept if that version is replaced.
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(12), default=BatchStatus.PENDING.value)
    requested_count: Mapped[int]
    # What was asked for: a list of categories (None means any) and a difficulty.
    categories: Mapped[list | None] = mapped_column(JSONB)
    difficulty: Mapped[str | None] = mapped_column(String(20))
    question_count: Mapped[int] = mapped_column(default=0)
    model: Mapped[str | None] = mapped_column(String(80))
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InterviewQuestion(Base):
    """A question an interviewer might ask about the project, with checked answer points.

    Questions belong to the repository, so progress survives a refresh. `analysis_version`
    says which version they were written from, since line numbers may have moved since.
    """

    __tablename__ = "interview_questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    saved_repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("saved_repositories.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_batches.id", ondelete="CASCADE"), index=True
    )
    analysis_version: Mapped[int]
    position: Mapped[int]  # order within the repository's questions
    category: Mapped[str] = mapped_column(String(30))
    difficulty: Mapped[str] = mapped_column(String(20))
    question: Mapped[str] = mapped_column(Text)
    why_asked: Mapped[str] = mapped_column(Text, default="")
    # Checked findings (see services/ai/schemas.Finding): the points a good answer covers.
    answer_points: Mapped[list] = mapped_column(JSONB, default=list)
    follow_ups: Mapped[list] = mapped_column(JSONB, default=list)
    # True when at least one answer point is backed by a confirmed quote from the code.
    grounded: Mapped[bool] = mapped_column(default=False)
    removed_citations: Mapped[int] = mapped_column(default=0)

    # --- the person's progress ---
    status: Mapped[str] = mapped_column(String(12), default=Progress.NEW.value)
    user_answer: Mapped[str | None] = mapped_column(Text)
    practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

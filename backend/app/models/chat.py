"""Conversations about one analyzed version of a repository."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Tied to an analysis, not the repository: answers cite lines of that exact version.
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(120))  # the first question, shortened
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessageStatus(StrEnum):
    PENDING = "pending"  # an answer is being written
    COMPLETED = "completed"
    FAILED = "failed"


class ChatMessage(Base):
    """A question (role "user") or an answer (role "assistant")."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="role"),
        UniqueConstraint("session_id", "position", name="uq_chat_messages_session_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    # Order within the conversation. A question and its answer are created in the same
    # transaction, so their timestamps can be equal and cannot be used for ordering.
    position: Mapped[int]
    role: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(12), default=MessageStatus.COMPLETED.value)
    # The question, or the checked answer text.
    content: Mapped[str] = mapped_column(Text, default="")
    # For answers: citations, the excerpts that were searched, and how it was checked
    # (see services/rag/schemas.py). Never the model's raw output.
    details: Mapped[dict | None] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(String(80))
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

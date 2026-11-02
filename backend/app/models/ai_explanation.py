import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiStatus(StrEnum):
    PENDING = "pending"  # a background job owns it
    COMPLETED = "completed"
    FAILED = "failed"


class AiKind(StrEnum):
    OVERVIEW = "overview"
    TECHNOLOGIES = "technologies"
    FILE = "file"


class AiExplanation(Base):
    """One AI-written explanation of an analysis (or of one file in it), after checking."""

    __tablename__ = "ai_explanations"
    __table_args__ = (
        # One explanation per analysis, kind and file. Regenerating replaces the row.
        UniqueConstraint(
            "analysis_id", "kind", "target_path", name="uq_ai_explanations_analysis_kind_path"
        ),
        CheckConstraint("kind IN ('overview', 'technologies', 'file')", name="kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    # The file path for kind "file"; an empty string otherwise (so the unique constraint
    # also works for the kinds that have no file).
    target_path: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(String(12), default=AiStatus.PENDING.value)
    # The checked result (see services/ai/schemas.py). Never the model's raw output.
    content: Mapped[dict | None] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(String(80))
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisFile(Base):
    """A file found in one analysis: either stored on disk, or skipped with a reason."""

    __tablename__ = "analysis_files"
    __table_args__ = (
        UniqueConstraint("analysis_id", "path", name="uq_analysis_files_analysis_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="CASCADE"), index=True
    )
    # Always relative to the repository root and "/"-separated.
    path: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(40))
    size_bytes: Mapped[int]
    line_count: Mapped[int | None]
    # None means the file was stored and can be read; otherwise why it was left out.
    skipped_reason: Mapped[str | None] = mapped_column(String(30))

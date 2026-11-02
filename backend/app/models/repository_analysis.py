import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import func as sql_func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    FETCHING = "fetching"  # talking to GitHub, downloading the archive
    EXTRACTING = "extracting"  # unpacking, filtering and storing files
    ANALYZING = "analyzing"  # parsing code, reading dependencies, detecting frameworks
    COMPLETED = "completed"
    FAILED = "failed"


# Statuses where a background job still owns the analysis.
IN_PROGRESS_STATUSES = (
    AnalysisStatus.QUEUED,
    AnalysisStatus.FETCHING,
    AnalysisStatus.EXTRACTING,
    AnalysisStatus.ANALYZING,
)


class RepositoryAnalysis(Base):
    """One analysis run of a saved repository. Refreshing creates a new version."""

    __tablename__ = "repository_analyses"
    __table_args__ = (
        UniqueConstraint(
            "saved_repository_id", "version", name="uq_repository_analyses_repository_version"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    saved_repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("saved_repositories.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default=AnalysisStatus.QUEUED.value)

    # Set only when status is "failed". The message is written for end users.
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(Text)

    commit_sha: Mapped[str | None] = mapped_column(String(40))
    # Selected fields from the GitHub API (description, stars, default branch...).
    github_metadata: Mapped[dict | None] = mapped_column(JSONB)
    # Bytes of code per language, as reported by GitHub.
    languages: Mapped[dict | None] = mapped_column(JSONB)

    # Frameworks and tools found, each with the evidence for it (see services/analysis).
    technologies: Mapped[list | None] = mapped_column(JSONB)
    # Per-language file/line counts and totals (symbols, imports, dependencies, ...).
    code_stats: Mapped[dict | None] = mapped_column(JSONB)

    readme_path: Mapped[str | None] = mapped_column(String(255))
    readme_text: Mapped[str | None] = mapped_column(Text)

    file_count: Mapped[int] = mapped_column(default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    # Counts of files that were skipped, by reason ({"binary": 12, "sensitive": 1}).
    skipped_summary: Mapped[dict | None] = mapped_column(JSONB)
    redaction_count: Mapped[int] = mapped_column(default=0)
    # True when a size or file-count limit stopped the import early.
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    # True once a newer version replaced this one and its stored files were deleted to
    # save space. The record and its file list stay, for refresh history.
    source_removed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sql_func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedRepository(Base):
    """A repository in one user's library. Every row belongs to exactly one user."""

    __tablename__ = "saved_repositories"
    __table_args__ = (
        # One library entry per user and source, enforced by the database so two
        # simultaneous requests cannot both insert it.
        UniqueConstraint("user_id", "source_key", name="uq_saved_repositories_user_id_source_key"),
        CheckConstraint("source_type IN ('github', 'zip')", name="source_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(16))
    # Lowercase identity of the source, e.g. "github:owner/repo". GitHub treats
    # names case-insensitively, so this is what duplicate detection compares.
    source_key: Mapped[str] = mapped_column(String(400))
    source_url: Mapped[str | None] = mapped_column(String(500))
    owner: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    # The person's own tags ("backend", "to review"), kept in the order they were added.
    labels: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

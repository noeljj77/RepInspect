"""What people add to their library: notes on a repository, and collections of repositories."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RepositoryNote(Base):
    """A note about a repository, optionally about one file (and line) in it.

    Notes belong to the repository, not to an analysis, so they survive a refresh. The
    path and line may then point at code that has moved; the page links them anyway.
    """

    __tablename__ = "repository_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    saved_repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("saved_repositories.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    path: Mapped[str | None] = mapped_column(Text)
    line: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Collection(Base):
    """A named group of repositories, such as "Interview: Acme" or "Python projects"."""

    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_collections_user_id_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CollectionRepository(Base):
    """Membership of a repository in a collection. A repository can be in several."""

    __tablename__ = "collection_repositories"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    saved_repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("saved_repositories.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

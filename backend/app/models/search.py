"""The search index behind chat: code chunks, and the state of building their vectors."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Computed, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IndexStatus(StrEnum):
    PENDING = "pending"  # waiting for a worker
    BUILDING = "building"  # chunking and embedding
    READY = "ready"
    FAILED = "failed"


class SearchIndex(Base):
    """One per analysis. The vectors themselves live in a FAISS file on disk."""

    __tablename__ = "search_indexes"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(12), default=IndexStatus.PENDING.value)
    # The embedding model that made the vectors. Queries must use the same one.
    model: Mapped[str | None] = mapped_column(String(120))
    dimension: Mapped[int | None]
    chunk_count: Mapped[int] = mapped_column(default=0)
    chunks_embedded: Mapped[int] = mapped_column(default=0)  # progress while building
    # True when the chunk limit stopped indexing before the end of the repository.
    truncated: Mapped[bool] = mapped_column(default=False)
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# Weighted so a match in the file path or symbol name counts more than one in the body.
SEARCH_VECTOR_SQL = (
    "setweight(to_tsvector('english'::regconfig, coalesce(symbol, '') || ' ' || path), 'A')"
    " || setweight(to_tsvector('english'::regconfig, keywords), 'B')"
    " || setweight(to_tsvector('english'::regconfig, content), 'C')"
)


class CodeChunk(Base):
    """A searchable piece of a file: usually one function, class or README section."""

    __tablename__ = "code_chunks"
    __table_args__ = (
        UniqueConstraint("analysis_id", "ordinal", name="uq_code_chunks_analysis_ordinal"),
        Index("ix_code_chunks_search", "search", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_files.id", ondelete="CASCADE"), index=True
    )
    # Position in the FAISS index: vector number N belongs to the chunk with ordinal N.
    ordinal: Mapped[int]
    path: Mapped[str] = mapped_column(Text)
    start_line: Mapped[int]
    end_line: Mapped[int]
    symbol: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    # Identifiers split into words (getUserById → get user by id) for keyword search.
    keywords: Mapped[str] = mapped_column(Text, default="")
    # Kept up to date by Postgres itself from the columns above.
    search: Mapped[str] = mapped_column(TSVECTOR, Computed(SEARCH_VECTOR_SQL, persisted=True))

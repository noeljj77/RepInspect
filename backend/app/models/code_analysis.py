"""Rows produced by static analysis: symbols, imports and declared dependencies."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CodeSymbol(Base):
    """A function, class, method, interface, enum or type alias found in a file."""

    __tablename__ = "code_symbols"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_files.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(Text)
    # Includes the enclosing class, e.g. "UserService.create".
    qualified_name: Mapped[str] = mapped_column(Text)
    start_line: Mapped[int]
    end_line: Mapped[int]
    signature: Mapped[str] = mapped_column(Text)
    doc: Mapped[str | None] = mapped_column(Text)
    decorators: Mapped[list | None] = mapped_column(JSONB)


class CodeImport(Base):
    """One import statement. `resolved_file_id` is set when it points at another file
    in the same repository, which is what builds the relationships between files."""

    __tablename__ = "code_imports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_files.id", ondelete="CASCADE"), index=True
    )
    module: Mapped[str] = mapped_column(Text)
    names: Mapped[list | None] = mapped_column(JSONB)
    line: Mapped[int]
    resolved_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_files.id", ondelete="SET NULL"), index=True
    )


class ProjectDependency(Base):
    """A dependency declared in a manifest (requirements.txt, package.json, pom.xml...)."""

    __tablename__ = "dependencies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="CASCADE"), index=True
    )
    ecosystem: Mapped[str] = mapped_column(String(10))  # pypi, npm or maven
    name: Mapped[str] = mapped_column(Text)
    version_spec: Mapped[str | None] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(12))  # runtime, dev, optional, peer, ...
    source_file: Mapped[str] = mapped_column(Text)
    line: Mapped[int | None]

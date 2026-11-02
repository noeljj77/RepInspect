"""add static analysis results

Revision ID: 324f9c1f4e01
Revises: fe31855411b5
Create Date: 2026-11-02 12:45:09.604771
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "324f9c1f4e01"
down_revision: str | None = "fe31855411b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dependencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("ecosystem", sa.String(length=10), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version_spec", sa.Text(), nullable=True),
        sa.Column("scope", sa.String(length=12), nullable=False),
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["repository_analyses.id"],
            name=op.f("fk_dependencies_analysis_id_repository_analyses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dependencies")),
    )
    op.create_index(
        op.f("ix_dependencies_analysis_id"), "dependencies", ["analysis_id"], unique=False
    )
    op.create_table(
        "code_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("module", sa.Text(), nullable=False),
        sa.Column("names", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("line", sa.Integer(), nullable=False),
        sa.Column("resolved_file_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["repository_analyses.id"],
            name=op.f("fk_code_imports_analysis_id_repository_analyses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["analysis_files.id"],
            name=op.f("fk_code_imports_file_id_analysis_files"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_file_id"],
            ["analysis_files.id"],
            name=op.f("fk_code_imports_resolved_file_id_analysis_files"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_code_imports")),
    )
    op.create_index(
        op.f("ix_code_imports_analysis_id"), "code_imports", ["analysis_id"], unique=False
    )
    op.create_index(op.f("ix_code_imports_file_id"), "code_imports", ["file_id"], unique=False)
    op.create_index(
        op.f("ix_code_imports_resolved_file_id"), "code_imports", ["resolved_file_id"], unique=False
    )
    op.create_table(
        "code_symbols",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("doc", sa.Text(), nullable=True),
        sa.Column("decorators", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["repository_analyses.id"],
            name=op.f("fk_code_symbols_analysis_id_repository_analyses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["analysis_files.id"],
            name=op.f("fk_code_symbols_file_id_analysis_files"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_code_symbols")),
    )
    op.create_index(
        op.f("ix_code_symbols_analysis_id"), "code_symbols", ["analysis_id"], unique=False
    )
    op.create_index(op.f("ix_code_symbols_file_id"), "code_symbols", ["file_id"], unique=False)
    op.add_column(
        "analysis_files",
        sa.Column("importance_score", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "analysis_files",
        sa.Column("importance_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "analysis_files",
        sa.Column("symbol_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "analysis_files",
        sa.Column("parse_error", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "repository_analyses",
        sa.Column("technologies", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "repository_analyses",
        sa.Column("code_stats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("repository_analyses", "code_stats")
    op.drop_column("repository_analyses", "technologies")
    op.drop_column("analysis_files", "parse_error")
    op.drop_column("analysis_files", "symbol_count")
    op.drop_column("analysis_files", "importance_reasons")
    op.drop_column("analysis_files", "importance_score")
    op.drop_index(op.f("ix_code_symbols_file_id"), table_name="code_symbols")
    op.drop_index(op.f("ix_code_symbols_analysis_id"), table_name="code_symbols")
    op.drop_table("code_symbols")
    op.drop_index(op.f("ix_code_imports_resolved_file_id"), table_name="code_imports")
    op.drop_index(op.f("ix_code_imports_file_id"), table_name="code_imports")
    op.drop_index(op.f("ix_code_imports_analysis_id"), table_name="code_imports")
    op.drop_table("code_imports")
    op.drop_index(op.f("ix_dependencies_analysis_id"), table_name="dependencies")
    op.drop_table("dependencies")

"""create repository tables

Revision ID: fe31855411b5
Revises: 0b36d6c28829
Create Date: 2026-11-02 12:11:42.824038
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "fe31855411b5"
down_revision: str | None = "0b36d6c28829"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_repositories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_key", sa.String(length=400), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("owner", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('github', 'zip')", name=op.f("ck_saved_repositories_source_type")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_saved_repositories_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_repositories")),
        sa.UniqueConstraint(
            "user_id", "source_key", name="uq_saved_repositories_user_id_source_key"
        ),
    )
    op.create_index(
        op.f("ix_saved_repositories_user_id"), "saved_repositories", ["user_id"], unique=False
    )
    op.create_table(
        "repository_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("saved_repository_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("commit_sha", sa.String(length=40), nullable=True),
        sa.Column("github_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("languages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("readme_path", sa.String(length=255), nullable=True),
        sa.Column("readme_text", sa.Text(), nullable=True),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False),
        sa.Column("skipped_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("redaction_count", sa.Integer(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["saved_repository_id"],
            ["saved_repositories.id"],
            name=op.f("fk_repository_analyses_saved_repository_id_saved_repositories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_analyses")),
        sa.UniqueConstraint(
            "saved_repository_id", "version", name="uq_repository_analyses_repository_version"
        ),
    )
    op.create_index(
        op.f("ix_repository_analyses_saved_repository_id"),
        "repository_analyses",
        ["saved_repository_id"],
        unique=False,
    )
    op.create_table(
        "analysis_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=40), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=True),
        sa.Column("skipped_reason", sa.String(length=30), nullable=True),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["repository_analyses.id"],
            name=op.f("fk_analysis_files_analysis_id_repository_analyses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_files")),
        sa.UniqueConstraint("analysis_id", "path", name="uq_analysis_files_analysis_path"),
    )
    op.create_index(
        op.f("ix_analysis_files_analysis_id"), "analysis_files", ["analysis_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_analysis_files_analysis_id"), table_name="analysis_files")
    op.drop_table("analysis_files")
    op.drop_index(
        op.f("ix_repository_analyses_saved_repository_id"), table_name="repository_analyses"
    )
    op.drop_table("repository_analyses")
    op.drop_index(op.f("ix_saved_repositories_user_id"), table_name="saved_repositories")
    op.drop_table("saved_repositories")

"""add library features

Revision ID: f177378e1e59
Revises: 12a469843665
Create Date: 2026-11-03 01:46:59.083279
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f177378e1e59"
down_revision: str | None = "12a469843665"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_collections_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collections")),
        sa.UniqueConstraint("user_id", "name", name="uq_collections_user_id_name"),
    )
    op.create_index(op.f("ix_collections_user_id"), "collections", ["user_id"], unique=False)
    op.create_table(
        "collection_repositories",
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("saved_repository_id", sa.Uuid(), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["collections.id"],
            name=op.f("fk_collection_repositories_collection_id_collections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["saved_repository_id"],
            ["saved_repositories.id"],
            name=op.f("fk_collection_repositories_saved_repository_id_saved_repositories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "collection_id", "saved_repository_id", name=op.f("pk_collection_repositories")
        ),
    )
    op.create_index(
        op.f("ix_collection_repositories_saved_repository_id"),
        "collection_repositories",
        ["saved_repository_id"],
        unique=False,
    )
    op.create_table(
        "repository_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("saved_repository_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("line", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["saved_repository_id"],
            ["saved_repositories.id"],
            name=op.f("fk_repository_notes_saved_repository_id_saved_repositories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_notes")),
    )
    op.create_index(
        op.f("ix_repository_notes_saved_repository_id"),
        "repository_notes",
        ["saved_repository_id"],
        unique=False,
    )
    op.add_column("analysis_files", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "repository_analyses",
        sa.Column("source_removed", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "saved_repositories",
        sa.Column(
            "labels", postgresql.ARRAY(sa.String(length=40)), server_default="{}", nullable=False
        ),
    )
    # Keep any existing single label as the first of the new list.
    op.execute("UPDATE saved_repositories SET labels = ARRAY[label] WHERE label IS NOT NULL")
    op.drop_column("saved_repositories", "label")


def downgrade() -> None:
    op.add_column(
        "saved_repositories",
        sa.Column("label", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
    )
    op.execute("UPDATE saved_repositories SET label = left(labels[1], 120)")
    op.drop_column("saved_repositories", "labels")
    op.drop_column("repository_analyses", "source_removed")
    op.drop_column("analysis_files", "content_hash")
    op.drop_index(op.f("ix_repository_notes_saved_repository_id"), table_name="repository_notes")
    op.drop_table("repository_notes")
    op.drop_index(
        op.f("ix_collection_repositories_saved_repository_id"), table_name="collection_repositories"
    )
    op.drop_table("collection_repositories")
    op.drop_index(op.f("ix_collections_user_id"), table_name="collections")
    op.drop_table("collections")

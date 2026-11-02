"""add ai explanations

Revision ID: ecbdb51c997f
Revises: 324f9c1f4e01
Create Date: 2026-11-02 21:09:04.504336
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ecbdb51c997f"
down_revision: str | None = "324f9c1f4e01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_explanations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("target_path", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('overview', 'technologies', 'file')", name=op.f("ck_ai_explanations_kind")
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["repository_analyses.id"],
            name=op.f("fk_ai_explanations_analysis_id_repository_analyses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_explanations")),
        sa.UniqueConstraint(
            "analysis_id", "kind", "target_path", name="uq_ai_explanations_analysis_kind_path"
        ),
    )
    op.create_index(
        op.f("ix_ai_explanations_analysis_id"), "ai_explanations", ["analysis_id"], unique=False
    )
    op.create_table(
        "ai_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ai_requests_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_requests")),
    )
    op.create_index(
        "ix_ai_requests_user_id_created_at", "ai_requests", ["user_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_ai_requests_user_id_created_at", table_name="ai_requests")
    op.drop_table("ai_requests")
    op.drop_index(op.f("ix_ai_explanations_analysis_id"), table_name="ai_explanations")
    op.drop_table("ai_explanations")

"""add interview preparation

Revision ID: 54b5d1d4bbe2
Revises: f177378e1e59
Create Date: 2026-11-03 11:53:21.304920
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "54b5d1d4bbe2"
down_revision: str | None = "f177378e1e59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("saved_repository_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("categories", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["repository_analyses.id"],
            name=op.f("fk_question_batches_analysis_id_repository_analyses"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["saved_repository_id"],
            ["saved_repositories.id"],
            name=op.f("fk_question_batches_saved_repository_id_saved_repositories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_batches")),
    )
    op.create_index(
        op.f("ix_question_batches_saved_repository_id"),
        "question_batches",
        ["saved_repository_id"],
        unique=False,
    )
    op.create_table(
        "interview_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("saved_repository_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_version", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("why_asked", sa.Text(), nullable=False),
        sa.Column("answer_points", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("follow_ups", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("grounded", sa.Boolean(), nullable=False),
        sa.Column("removed_citations", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=True),
        sa.Column("practiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["question_batches.id"],
            name=op.f("fk_interview_questions_batch_id_question_batches"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["saved_repository_id"],
            ["saved_repositories.id"],
            name=op.f("fk_interview_questions_saved_repository_id_saved_repositories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interview_questions")),
    )
    op.create_index(
        op.f("ix_interview_questions_batch_id"), "interview_questions", ["batch_id"], unique=False
    )
    op.create_index(
        op.f("ix_interview_questions_saved_repository_id"),
        "interview_questions",
        ["saved_repository_id"],
        unique=False,
    )

    # Interview notes are a new kind of AI explanation. (Autogenerate does not see changes
    # to check constraints, so this is written by hand.)
    op.drop_constraint(op.f("ck_ai_explanations_kind"), "ai_explanations", type_="check")
    op.create_check_constraint(
        op.f("ck_ai_explanations_kind"),
        "ai_explanations",
        "kind IN ('overview', 'technologies', 'file', 'report')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM ai_explanations WHERE kind = 'report'")
    op.drop_constraint(op.f("ck_ai_explanations_kind"), "ai_explanations", type_="check")
    op.create_check_constraint(
        op.f("ck_ai_explanations_kind"),
        "ai_explanations",
        "kind IN ('overview', 'technologies', 'file')",
    )
    op.drop_index(
        op.f("ix_interview_questions_saved_repository_id"), table_name="interview_questions"
    )
    op.drop_index(op.f("ix_interview_questions_batch_id"), table_name="interview_questions")
    op.drop_table("interview_questions")
    op.drop_index(op.f("ix_question_batches_saved_repository_id"), table_name="question_batches")
    op.drop_table("question_batches")

"""add mock interviews

Revision ID: aca6ea7d2032
Revises: 54b5d1d4bbe2
Create Date: 2026-11-03 12:06:46.467209
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "aca6ea7d2032"
down_revision: str | None = "54b5d1d4bbe2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mock_interviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("saved_repository_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("categories", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
            name=op.f("fk_mock_interviews_analysis_id_repository_analyses"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["saved_repository_id"],
            ["saved_repositories.id"],
            name=op.f("fk_mock_interviews_saved_repository_id_saved_repositories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mock_interviews")),
    )
    op.create_index(
        op.f("ix_mock_interviews_saved_repository_id"),
        "mock_interviews",
        ["saved_repository_id"],
        unique=False,
    )
    op.create_table(
        "mock_interview_turns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("reference_points", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("grade", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["interview_id"],
            ["mock_interviews.id"],
            name=op.f("fk_mock_interview_turns_interview_id_mock_interviews"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["interview_questions.id"],
            name=op.f("fk_mock_interview_turns_question_id_interview_questions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mock_interview_turns")),
        sa.UniqueConstraint("interview_id", "position", name="uq_mock_interview_turns_position"),
    )
    op.create_index(
        op.f("ix_mock_interview_turns_interview_id"),
        "mock_interview_turns",
        ["interview_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mock_interview_turns_interview_id"), table_name="mock_interview_turns")
    op.drop_table("mock_interview_turns")
    op.drop_index(op.f("ix_mock_interviews_saved_repository_id"), table_name="mock_interviews")
    op.drop_table("mock_interviews")

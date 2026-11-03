"""add revoked tokens

Revision ID: 7c1e5a9d2b40
Revises: aca6ea7d2032
Create Date: 2026-11-03 14:56:43.491126
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7c1e5a9d2b40"
down_revision: str | None = "aca6ea7d2032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index(op.f("ix_revoked_tokens_expires_at"), "revoked_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_revoked_tokens_expires_at"), table_name="revoked_tokens")
    op.drop_table("revoked_tokens")

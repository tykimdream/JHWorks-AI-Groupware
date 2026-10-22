"""add a singleton shared login budget

Revision ID: c84f2a19d6e0
Revises: b63d91e52fa0
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c84f2a19d6e0"
down_revision: str | None = "b63d91e52fa0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_budget",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("window_number", sa.BigInteger(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_login_budget_singleton"),
        sa.CheckConstraint("window_number >= 0", name="ck_login_budget_window"),
        sa.CheckConstraint("attempts >= 1", name="ck_login_budget_attempts"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("login_budget")

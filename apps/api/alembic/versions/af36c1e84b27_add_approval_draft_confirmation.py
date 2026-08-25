"""add approval draft confirmation

Revision ID: af36c1e84b27
Revises: d92a5f6e10bc
Create Date: 2026-08-25 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "af36c1e84b27"
down_revision: str | None = "d92a5f6e10bc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("approvals") as batch_op:
        batch_op.add_column(
            sa.Column("source_confirmation_id", sa.String(length=64), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_approvals_source_confirmation_id",
            ["source_confirmation_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("approvals") as batch_op:
        batch_op.drop_constraint(
            "uq_approvals_source_confirmation_id",
            type_="unique",
        )
        batch_op.drop_column("source_confirmation_id")

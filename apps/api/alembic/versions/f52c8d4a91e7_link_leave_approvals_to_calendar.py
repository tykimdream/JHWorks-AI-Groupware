"""link leave approvals to calendar

Revision ID: f52c8d4a91e7
Revises: e41b7a9c30d2
Create Date: 2026-08-25 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f52c8d4a91e7"
down_revision: str | None = "e41b7a9c30d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("work_calendar_events") as batch_op:
        batch_op.add_column(sa.Column("approval_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_work_calendar_events_approval_id_approvals",
            "approvals",
            ["approval_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_unique_constraint(
            "uq_work_calendar_events_approval_id",
            ["approval_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("work_calendar_events") as batch_op:
        batch_op.drop_constraint("uq_work_calendar_events_approval_id", type_="unique")
        batch_op.drop_constraint(
            "fk_work_calendar_events_approval_id_approvals",
            type_="foreignkey",
        )
        batch_op.drop_column("approval_id")

"""add inactive AI admission and settlement ledger

Revision ID: a14c7e2d903f
Revises: f30c9a71b624
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a14c7e2d903f"
down_revision: str | None = "f30c9a71b624"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_budget_counters",
        sa.Column("key", sa.String(160), primary_key=True),
        sa.Column("reserved_micro_usd", sa.BigInteger(), nullable=False),
        sa.Column("spent_micro_usd", sa.BigInteger(), nullable=False),
        sa.Column("admissions", sa.Integer(), nullable=False),
        sa.Column("active_requests", sa.Integer(), nullable=False),
        sa.Column("last_observed_epoch", sa.BigInteger(), nullable=False),
        sa.Column("is_frozen", sa.Boolean(), nullable=False),
        sa.CheckConstraint("reserved_micro_usd >= 0", name="ck_ai_counter_reserved"),
        sa.CheckConstraint("spent_micro_usd >= 0", name="ck_ai_counter_spent"),
        sa.CheckConstraint("admissions >= 0", name="ck_ai_counter_admissions"),
        sa.CheckConstraint("active_requests >= 0", name="ck_ai_counter_active"),
        sa.CheckConstraint("last_observed_epoch >= 0", name="ck_ai_counter_clock"),
    )
    op.create_table(
        "ai_budget_reservations",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column(
            "day_key", sa.String(160), sa.ForeignKey("ai_budget_counters.key"), nullable=False
        ),
        sa.Column(
            "month_key", sa.String(160), sa.ForeignKey("ai_budget_counters.key"), nullable=False
        ),
        sa.Column(
            "scope_key", sa.String(160), sa.ForeignKey("ai_budget_counters.key"), nullable=False
        ),
        sa.Column("maximum_micro_usd", sa.BigInteger(), nullable=False),
        sa.Column("charged_micro_usd", sa.BigInteger(), nullable=True),
        sa.Column("created_at_epoch", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="RESERVED"),
        sa.CheckConstraint("maximum_micro_usd > 0", name="ck_ai_reservation_maximum"),
        sa.CheckConstraint("created_at_epoch > 0", name="ck_ai_reservation_created"),
        sa.CheckConstraint(
            "status IN ('RESERVED', 'SETTLED', 'UNCERTAIN', 'OVERRUN')",
            name="ck_ai_reservation_status",
        ),
        sa.CheckConstraint(
            "(status = 'RESERVED' AND charged_micro_usd IS NULL) OR "
            "(status <> 'RESERVED' AND charged_micro_usd IS NOT NULL AND charged_micro_usd >= 0)",
            name="ck_ai_reservation_charge",
        ),
    )


def downgrade() -> None:
    if op.get_context().as_sql or any(
        op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).scalar() is not None
        for table in ("ai_budget_reservations", "ai_budget_counters")
    ):
        raise RuntimeError("Cannot drop AI accounting while budget records exist")
    op.drop_table("ai_budget_reservations")
    op.drop_table("ai_budget_counters")

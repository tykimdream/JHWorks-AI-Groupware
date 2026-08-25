"""add structured policy rules

Revision ID: d92a5f6e10bc
Revises: c7f3a91d42e8
Create Date: 2026-08-25 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d92a5f6e10bc"
down_revision: str | None = "c7f3a91d42e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POLICY_RULES: dict[str, dict[str, object]] = {
    "TRAVEL-1": {"kind": "MAX_LODGING_PER_NIGHT", "limitKrw": 120000},
    "TRAVEL-2": {"kind": "ATTACHMENT_REQUIRED_WHEN_COST_POSITIVE", "costField": "transportation"},
    "TRAVEL-3": {"kind": "PRIOR_APPROVAL_MIN_TOTAL", "thresholdKrw": 300000},
    "EXPENSE-2": {"kind": "RECEIPT_REQUIRED_MIN_TOTAL", "thresholdKrw": 100000},
    "EXPENSE-3": {"kind": "PRIOR_APPROVAL_MIN_TOTAL", "thresholdKrw": 300000},
}


def upgrade() -> None:
    op.add_column("policy_sections", sa.Column("rule_config", sa.JSON(), nullable=True))
    sections = sa.table(
        "policy_sections",
        sa.column("section_id", sa.String()),
        sa.column("rule_config", sa.JSON()),
    )
    for section_id, rule in POLICY_RULES.items():
        op.execute(
            sections.update().where(sections.c.section_id == section_id).values(rule_config=rule)
        )


def downgrade() -> None:
    op.drop_column("policy_sections", "rule_config")

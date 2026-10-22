"""add bounded demo provisioning and all-request admission

Revision ID: e29b73a65f10
Revises: d17a8b5e903c
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e29b73a65f10"
down_revision: str | None = "d17a8b5e903c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_start_budget",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("day_number", sa.BigInteger(), nullable=False),
        sa.Column("starts_used", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_demo_start_singleton"),
        sa.CheckConstraint("day_number >= 0", name="ck_demo_start_day"),
        sa.CheckConstraint("starts_used >= 1", name="ck_demo_start_usage"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("demo_workspaces") as batch:
        batch.add_column(
            sa.Column("request_limit", sa.Integer(), server_default="100", nullable=False)
        )
        batch.add_column(
            sa.Column("requests_used", sa.Integer(), server_default="0", nullable=False)
        )
        batch.create_check_constraint(
            "ck_demo_workspace_requests_limit", "request_limit BETWEEN 1 AND 500"
        )
        batch.create_check_constraint(
            "ck_demo_workspace_requests_usage",
            "requests_used >= 0 AND requests_used <= request_limit",
        )


def downgrade() -> None:
    if (
        op.get_context().as_sql
        or op.get_bind().execute(sa.text("SELECT 1 FROM demo_workspaces LIMIT 1")).scalar()
        is not None
    ):
        raise RuntimeError("Cannot remove workspace protection while demo workspaces exist")
    with op.batch_alter_table("demo_workspaces") as batch:
        batch.drop_constraint("ck_demo_workspace_requests_usage", type_="check")
        batch.drop_constraint("ck_demo_workspace_requests_limit", type_="check")
        batch.drop_column("requests_used")
        batch.drop_column("request_limit")
    op.drop_table("demo_start_budget")

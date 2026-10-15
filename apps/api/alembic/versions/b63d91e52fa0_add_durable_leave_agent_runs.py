"""add durable leave agent runs

Revision ID: b63d91e52fa0
Revises: f52c8d4a91e7
Create Date: 2026-08-25 17:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b63d91e52fa0"
down_revision: str | None = "f52c8d4a91e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_agent_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("approval_id", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "CONSULTING",
                "NEEDS_INPUT",
                "CONSULTATION_FAILED",
                "CANDIDATES_READY",
                "AWAITING_DRAFT_CONFIRMATION",
                "DRAFT_CREATED",
                "AWAITING_SUBMIT_CONFIRMATION",
                "SUBMITTING",
                "SUBMITTED",
                "CANCELED",
                "EXPIRED",
                "STALE",
                "FAILED",
                name="leaveagentstatus",
                native_enum=False,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("consultation_result", sa.JSON(), nullable=True),
        sa.Column("draft_preview", sa.JSON(), nullable=True),
        sa.Column("submit_preview", sa.JSON(), nullable=True),
        sa.Column("submit_confirmation_id", sa.String(length=64), nullable=True),
        sa.Column("submit_confirmation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("trace", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "submit_confirmation_id",
            name="uq_leave_agent_runs_submit_confirmation_id",
        ),
    )
    op.create_index(
        op.f("ix_leave_agent_runs_actor_id"),
        "leave_agent_runs",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leave_agent_runs_approval_id"),
        "leave_agent_runs",
        ["approval_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leave_agent_runs_status"),
        "leave_agent_runs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_leave_agent_runs_status"), table_name="leave_agent_runs")
    op.drop_index(op.f("ix_leave_agent_runs_approval_id"), table_name="leave_agent_runs")
    op.drop_index(op.f("ix_leave_agent_runs_actor_id"), table_name="leave_agent_runs")
    op.drop_table("leave_agent_runs")

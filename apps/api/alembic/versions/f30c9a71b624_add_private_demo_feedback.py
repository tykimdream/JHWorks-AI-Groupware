"""add private bounded demo feedback

Revision ID: f30c9a71b624
Revises: e29b73a65f10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f30c9a71b624"
down_revision: str | None = "e29b73a65f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_feedback_gate",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_demo_feedback_gate_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "demo_feedback",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("workspace_hash", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("screen", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at_epoch", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_hash"),
    )
    op.create_index("ix_demo_feedback_created_at_epoch", "demo_feedback", ["created_at_epoch"])


def downgrade() -> None:
    if (
        op.get_context().as_sql
        or op.get_bind().execute(sa.text("SELECT 1 FROM demo_feedback LIMIT 1")).scalar()
        is not None
    ):
        raise RuntimeError("Cannot drop feedback while retained submissions exist")
    op.drop_index("ix_demo_feedback_created_at_epoch", table_name="demo_feedback")
    op.drop_table("demo_feedback")
    op.drop_table("demo_feedback_gate")

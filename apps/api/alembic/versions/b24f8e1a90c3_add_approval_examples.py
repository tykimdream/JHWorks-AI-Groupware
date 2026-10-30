"""add curated synthetic approval examples

Revision ID: b24f8e1a90c3
Revises: a14c7e2d903f
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b24f8e1a90c3"
down_revision: str | None = "a14c7e2d903f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_examples",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("outline", sa.JSON(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("approval_examples")

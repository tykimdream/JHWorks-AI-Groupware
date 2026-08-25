"""add policy section embeddings

Revision ID: c7f3a91d42e8
Revises: 8f624aab11bf
Create Date: 2026-08-25 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR

from alembic import op

revision: str = "c7f3a91d42e8"
down_revision: str | None = "8f624aab11bf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    if is_postgresql:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    embedding_type: sa.types.TypeEngine[object]
    embedding_type = VECTOR(1536) if is_postgresql else sa.JSON()
    op.add_column("policy_sections", sa.Column("embedding", embedding_type, nullable=True))
    op.add_column(
        "policy_sections", sa.Column("embedding_model", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "policy_sections",
        sa.Column("embedded_content_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "policy_sections", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True)
    )

    if is_postgresql:
        op.create_index(
            "ix_policy_sections_embedding_hnsw",
            "policy_sections",
            ["embedding"],
            unique=False,
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=sa.text("embedding IS NOT NULL"),
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_index("ix_policy_sections_embedding_hnsw", table_name="policy_sections")
    op.drop_column("policy_sections", "indexed_at")
    op.drop_column("policy_sections", "embedded_content_hash")
    op.drop_column("policy_sections", "embedding_model")
    op.drop_column("policy_sections", "embedding")

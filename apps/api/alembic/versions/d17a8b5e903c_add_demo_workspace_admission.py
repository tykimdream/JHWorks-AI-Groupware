"""add server-managed demo workspace admission

Revision ID: d17a8b5e903c
Revises: c84f2a19d6e0
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d17a8b5e903c"
down_revision: str | None = "c84f2a19d6e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_workspaces",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("department_id", sa.String(64), nullable=False),
        sa.Column("expires_at_epoch", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("write_limit", sa.Integer(), nullable=False),
        sa.Column("writes_used", sa.Integer(), nullable=False),
        sa.CheckConstraint("expires_at_epoch > 0", name="ck_demo_workspace_expiry"),
        sa.CheckConstraint("write_limit BETWEEN 1 AND 100", name="ck_demo_workspace_limit"),
        sa.CheckConstraint(
            "writes_used >= 0 AND writes_used <= write_limit", name="ck_demo_workspace_usage"
        ),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("department_id"),
    )
    with op.batch_alter_table("employees") as batch:
        batch.add_column(sa.Column("demo_workspace_id", sa.String(64), nullable=True))
        batch.create_foreign_key(
            "fk_employee_demo_workspace", "demo_workspaces", ["demo_workspace_id"], ["id"]
        )
        batch.create_index(
            "ix_employees_department_demo_workspace", ["department_id", "demo_workspace_id"]
        )


def downgrade() -> None:
    if (
        op.get_context().as_sql
        or op.get_bind().execute(sa.text("SELECT 1 FROM demo_workspaces LIMIT 1")).scalar()
        is not None
    ):
        raise RuntimeError("Cannot remove workspace protection while demo workspaces exist")
    with op.batch_alter_table("employees") as batch:
        batch.drop_index("ix_employees_department_demo_workspace")
        batch.drop_constraint("fk_employee_demo_workspace", type_="foreignkey")
        batch.drop_column("demo_workspace_id")
    op.drop_table("demo_workspaces")

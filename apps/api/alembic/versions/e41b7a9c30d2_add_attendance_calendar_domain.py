"""add attendance calendar domain

Revision ID: e41b7a9c30d2
Revises: af36c1e84b27
Create Date: 2026-08-25 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e41b7a9c30d2"
down_revision: str | None = "af36c1e84b27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_accounts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("employee_id", sa.String(length=64), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("granted_days", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("carried_over_days", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("used_days", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("pending_days", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "used_days + pending_days <= granted_days + carried_over_days",
            name="ck_leave_account_available_non_negative",
        ),
        sa.CheckConstraint(
            "granted_days >= 0 AND carried_over_days >= 0 AND "
            "used_days >= 0 AND pending_days >= 0",
            name="ck_leave_account_non_negative",
        ),
        sa.CheckConstraint("version >= 1", name="ck_leave_account_version"),
        sa.CheckConstraint("year >= 2000 AND year <= 2100", name="ck_leave_account_year"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "year", name="uq_leave_account_employee_year"),
    )
    op.create_index(
        op.f("ix_leave_accounts_employee_id"), "leave_accounts", ["employee_id"], unique=False
    )
    op.create_index(op.f("ix_leave_accounts_year"), "leave_accounts", ["year"], unique=False)

    op.create_table(
        "work_calendar_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "COMPANY_EVENT",
                "PROJECT_MILESTONE",
                "HOLIDAY",
                "LEAVE",
                name="attendanceeventcategory",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "scope",
            sa.Enum(
                "COMPANY",
                "DEPARTMENT",
                "EMPLOYEE",
                name="attendanceeventscope",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("department_id", sa.String(length=64), nullable=True),
        sa.Column("employee_id", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "TENTATIVE",
                "CONFIRMED",
                "CANCELED",
                name="attendanceeventstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "impact",
            sa.Enum(
                "NONE",
                "CAUTION",
                "BLOCKED",
                name="attendanceimpact",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "end_date >= start_date", name="ck_work_calendar_event_date_order"
        ),
        sa.CheckConstraint(
            "(scope = 'COMPANY' AND department_id IS NULL AND employee_id IS NULL) OR "
            "(scope = 'DEPARTMENT' AND department_id IS NOT NULL AND employee_id IS NULL) OR "
            "(scope = 'EMPLOYEE' AND department_id IS NULL AND employee_id IS NOT NULL)",
            name="ck_work_calendar_event_scope_target",
        ),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "category",
        "start_date",
        "end_date",
        "scope",
        "department_id",
        "employee_id",
        "status",
    ):
        op.create_index(
            op.f(f"ix_work_calendar_events_{column}"),
            "work_calendar_events",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in (
        "status",
        "employee_id",
        "department_id",
        "scope",
        "end_date",
        "start_date",
        "category",
    ):
        op.drop_index(
            op.f(f"ix_work_calendar_events_{column}"),
            table_name="work_calendar_events",
        )
    op.drop_table("work_calendar_events")
    op.drop_index(op.f("ix_leave_accounts_year"), table_name="leave_accounts")
    op.drop_index(op.f("ix_leave_accounts_employee_id"), table_name="leave_accounts")
    op.drop_table("leave_accounts")

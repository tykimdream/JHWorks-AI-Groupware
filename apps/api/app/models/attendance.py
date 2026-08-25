from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    AttendanceEventCategory,
    AttendanceEventScope,
    AttendanceEventStatus,
    AttendanceImpact,
)

if TYPE_CHECKING:
    from app.models.approval import Approval
    from app.models.employee import Department, Employee


def utc_now() -> datetime:
    return datetime.now(UTC)


class LeaveAccount(Base):
    __tablename__ = "leave_accounts"
    __table_args__ = (
        UniqueConstraint("employee_id", "year", name="uq_leave_account_employee_year"),
        CheckConstraint("year >= 2000 AND year <= 2100", name="ck_leave_account_year"),
        CheckConstraint(
            "granted_days >= 0 AND carried_over_days >= 0 AND "
            "used_days >= 0 AND pending_days >= 0",
            name="ck_leave_account_non_negative",
        ),
        CheckConstraint(
            "used_days + pending_days <= granted_days + carried_over_days",
            name="ck_leave_account_available_non_negative",
        ),
        CheckConstraint("version >= 1", name="ck_leave_account_version"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    granted_days: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    carried_over_days: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False, default=0)
    used_days: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False, default=0)
    pending_days: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    employee: Mapped["Employee"] = relationship("Employee", back_populates="leave_accounts")

    @property
    def available_days(self) -> Decimal:
        return self.granted_days + self.carried_over_days - self.used_days - self.pending_days


class WorkCalendarEvent(Base):
    __tablename__ = "work_calendar_events"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_work_calendar_event_date_order"),
        CheckConstraint(
            "(scope = 'COMPANY' AND department_id IS NULL AND employee_id IS NULL) OR "
            "(scope = 'DEPARTMENT' AND department_id IS NOT NULL AND employee_id IS NULL) OR "
            "(scope = 'EMPLOYEE' AND department_id IS NULL AND employee_id IS NOT NULL)",
            name="ck_work_calendar_event_scope_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[AttendanceEventCategory] = mapped_column(
        Enum(AttendanceEventCategory, native_enum=False, length=32), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scope: Mapped[AttendanceEventScope] = mapped_column(
        Enum(AttendanceEventScope, native_enum=False, length=32), nullable=False, index=True
    )
    department_id: Mapped[str | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True, index=True
    )
    employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    approval_id: Mapped[str | None] = mapped_column(
        ForeignKey("approvals.id", ondelete="CASCADE"), nullable=True, unique=True
    )
    status: Mapped[AttendanceEventStatus] = mapped_column(
        Enum(AttendanceEventStatus, native_enum=False, length=32), nullable=False, index=True
    )
    impact: Mapped[AttendanceImpact] = mapped_column(
        Enum(AttendanceImpact, native_enum=False, length=32), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    department: Mapped["Department | None"] = relationship(
        "Department", foreign_keys=[department_id]
    )
    employee: Mapped["Employee | None"] = relationship(
        "Employee",
        back_populates="calendar_events",
        foreign_keys=[employee_id],
    )
    approval: Mapped["Approval | None"] = relationship(
        "Approval", back_populates="calendar_event", foreign_keys=[approval_id]
    )

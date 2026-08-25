from datetime import date, datetime
from decimal import Decimal

from app.core.schema import ApiSchema
from app.models.enums import (
    AttendanceEventCategory,
    AttendanceEventScope,
    AttendanceEventStatus,
    AttendanceImpact,
)


class AttendanceEmployeeRead(ApiSchema):
    id: str
    name: str
    position: str


class LeaveBalanceRead(ApiSchema):
    year: int
    granted_days: Decimal
    carried_over_days: Decimal
    used_days: Decimal
    pending_days: Decimal
    available_days: Decimal
    version: int
    updated_at: datetime


class WorkCalendarEventRead(ApiSchema):
    id: str
    category: AttendanceEventCategory
    title: str
    description: str | None
    start_date: date
    end_date: date
    scope: AttendanceEventScope
    status: AttendanceEventStatus
    impact: AttendanceImpact


class TeamLeaveRead(ApiSchema):
    id: str
    employee: AttendanceEmployeeRead
    start_date: date
    end_date: date
    status: AttendanceEventStatus
    impact: AttendanceImpact


class AttendanceOverviewRead(ApiSchema):
    range_start: date
    range_end: date
    leave_balances: list[LeaveBalanceRead]
    calendar_events: list[WorkCalendarEventRead]
    team_leaves: list[TeamLeaveRead]

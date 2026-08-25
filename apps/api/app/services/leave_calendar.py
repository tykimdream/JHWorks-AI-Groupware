from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.attendance import WorkCalendarEvent
from app.models.employee import Employee
from app.models.enums import (
    AttendanceEventCategory,
    AttendanceEventScope,
    AttendanceEventStatus,
)


def dates_between(start_date: date, end_date: date) -> list[date]:
    dates: list[date] = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def get_shared_events(
    db: Session,
    employee: Employee,
    start_date: date,
    end_date: date,
) -> list[WorkCalendarEvent]:
    return list(
        db.scalars(
            select(WorkCalendarEvent)
            .where(
                WorkCalendarEvent.start_date <= end_date,
                WorkCalendarEvent.end_date >= start_date,
                WorkCalendarEvent.status != AttendanceEventStatus.CANCELED,
                WorkCalendarEvent.scope != AttendanceEventScope.EMPLOYEE,
                or_(
                    WorkCalendarEvent.scope == AttendanceEventScope.COMPANY,
                    WorkCalendarEvent.department_id == employee.department_id,
                ),
            )
            .order_by(WorkCalendarEvent.start_date, WorkCalendarEvent.id)
        )
    )


def get_team_leave_events(
    db: Session,
    employee: Employee,
    start_date: date,
    end_date: date,
) -> list[WorkCalendarEvent]:
    return list(
        db.scalars(
            select(WorkCalendarEvent)
            .join(Employee, WorkCalendarEvent.employee_id == Employee.id)
            .options(joinedload(WorkCalendarEvent.employee))
            .where(
                WorkCalendarEvent.category == AttendanceEventCategory.LEAVE,
                WorkCalendarEvent.scope == AttendanceEventScope.EMPLOYEE,
                WorkCalendarEvent.status != AttendanceEventStatus.CANCELED,
                WorkCalendarEvent.start_date <= end_date,
                WorkCalendarEvent.end_date >= start_date,
                Employee.department_id == employee.department_id,
            )
            .order_by(WorkCalendarEvent.start_date, WorkCalendarEvent.id)
        )
    )


def confirmed_holiday_dates(
    events: list[WorkCalendarEvent],
    start_date: date,
    end_date: date,
) -> set[date]:
    holidays: set[date] = set()
    for event in events:
        if (
            event.category != AttendanceEventCategory.HOLIDAY
            or event.status != AttendanceEventStatus.CONFIRMED
        ):
            continue
        holidays.update(
            dates_between(max(start_date, event.start_date), min(end_date, event.end_date))
        )
    return holidays


def calculate_leave_days(
    db: Session,
    employee: Employee,
    start_date: date,
    end_date: date,
    leave_unit: str,
) -> Decimal | None:
    if start_date > end_date or start_date.year != end_date.year:
        return None

    shared_events = get_shared_events(db, employee, start_date, end_date)
    holiday_dates = confirmed_holiday_dates(shared_events, start_date, end_date)
    business_days = sum(
        current.weekday() < 5 and current not in holiday_dates
        for current in dates_between(start_date, end_date)
    )

    if leave_unit in {"HALF_DAY_AM", "HALF_DAY_PM"}:
        if start_date != end_date or business_days != 1:
            return None
        return Decimal("0.5")
    if leave_unit != "FULL_DAY" or business_days == 0:
        return None
    return Decimal(business_days).quantize(Decimal("0.1"))

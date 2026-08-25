from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attendance import LeaveAccount, WorkCalendarEvent
from app.models.employee import Employee
from app.schemas.attendance import (
    AttendanceEmployeeRead,
    AttendanceOverviewRead,
    LeaveBalanceRead,
    TeamLeaveRead,
    WorkCalendarEventRead,
)
from app.services.leave_calendar import get_shared_events, get_team_leave_events


def get_attendance_overview(
    db: Session,
    actor: Employee,
    start_date: date,
    end_date: date,
) -> AttendanceOverviewRead:
    years = range(start_date.year, end_date.year + 1)
    accounts = db.scalars(
        select(LeaveAccount)
        .where(LeaveAccount.employee_id == actor.id, LeaveAccount.year.in_(years))
        .order_by(LeaveAccount.year)
    )
    balances = [
        LeaveBalanceRead(
            year=account.year,
            granted_days=account.granted_days,
            carried_over_days=account.carried_over_days,
            used_days=account.used_days,
            pending_days=account.pending_days,
            available_days=account.available_days,
            version=account.version,
            updated_at=account.updated_at,
        )
        for account in accounts
    ]

    shared_events = get_shared_events(db, actor, start_date, end_date)
    team_leave_events = get_team_leave_events(db, actor, start_date, end_date)

    return AttendanceOverviewRead(
        range_start=start_date,
        range_end=end_date,
        leave_balances=balances,
        calendar_events=[WorkCalendarEventRead.model_validate(event) for event in shared_events],
        team_leaves=[_team_leave_read(event) for event in team_leave_events],
    )


def _team_leave_read(event: WorkCalendarEvent) -> TeamLeaveRead:
    employee = event.employee
    if employee is None:
        raise ValueError("Employee-scoped leave event has no employee")
    return TeamLeaveRead(
        id=event.id,
        employee=AttendanceEmployeeRead(
            id=employee.id,
            name=employee.name,
            position=employee.position,
        ),
        start_date=event.start_date,
        end_date=event.end_date,
        status=event.status,
        impact=event.impact,
    )

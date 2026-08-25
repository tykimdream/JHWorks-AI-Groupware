from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.attendance import LeaveAccount, WorkCalendarEvent
from app.models.employee import Employee
from app.models.enums import (
    AttendanceEventCategory,
    AttendanceEventScope,
    AttendanceEventStatus,
)
from app.schemas.attendance import (
    AttendanceEmployeeRead,
    AttendanceOverviewRead,
    LeaveBalanceRead,
    TeamLeaveRead,
    WorkCalendarEventRead,
)


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

    shared_events = db.scalars(
        select(WorkCalendarEvent)
        .where(
            WorkCalendarEvent.start_date <= end_date,
            WorkCalendarEvent.end_date >= start_date,
            WorkCalendarEvent.status != AttendanceEventStatus.CANCELED,
            WorkCalendarEvent.scope != AttendanceEventScope.EMPLOYEE,
            or_(
                WorkCalendarEvent.scope == AttendanceEventScope.COMPANY,
                WorkCalendarEvent.department_id == actor.department_id,
            ),
        )
        .order_by(WorkCalendarEvent.start_date, WorkCalendarEvent.id)
    )

    team_leave_events = db.scalars(
        select(WorkCalendarEvent)
        .join(Employee, WorkCalendarEvent.employee_id == Employee.id)
        .options(joinedload(WorkCalendarEvent.employee))
        .where(
            WorkCalendarEvent.category == AttendanceEventCategory.LEAVE,
            WorkCalendarEvent.scope == AttendanceEventScope.EMPLOYEE,
            WorkCalendarEvent.status != AttendanceEventStatus.CANCELED,
            WorkCalendarEvent.start_date <= end_date,
            WorkCalendarEvent.end_date >= start_date,
            Employee.department_id == actor.department_id,
        )
        .order_by(WorkCalendarEvent.start_date, WorkCalendarEvent.id)
    )

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

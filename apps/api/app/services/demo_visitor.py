"""Bounded anonymous demo provisioning, disabled unless explicitly configured."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings
from app.core.errors import AppError, AuthenticationError, ServiceUnavailableError
from app.core.security import decode_session_token
from app.models.attendance import LeaveAccount
from app.models.demo_start_budget import DemoStartBudget
from app.models.demo_workspace import DemoWorkspace
from app.models.employee import Department, Employee
from app.models.enums import EmployeeRole
from app.services.demo_workspace import require_demo_workspace
from app.services.login_budget import database_seconds


class DemoStartLimitError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "DEMO_START_LIMIT_REACHED",
            "Demo capacity is temporarily full. Please try again later.",
            429,
        )


def _load_actor(db: Session, employee_id: str) -> Employee:
    actor = db.scalar(
        select(Employee)
        .options(joinedload(Employee.department), joinedload(Employee.manager))
        .where(Employee.id == employee_id)
    )
    if actor is None or not actor.is_active or actor.demo_workspace_id is None:
        raise AuthenticationError("The demo visitor is unavailable")
    return actor


def start_visit(db: Session, settings: Settings, token: str | None = None) -> Employee:
    if token is not None:
        try:
            actor = _load_actor(db, decode_session_token(token))
            require_demo_workspace(db, actor)
            return actor
        except AuthenticationError:
            db.rollback()
    now = database_seconds(db)
    day = now // 86400
    insert = (
        pg_insert(DemoStartBudget)
        if db.get_bind().dialect.name == "postgresql"
        else sqlite_insert(DemoStartBudget)
    )
    newer_day = DemoStartBudget.day_number < day
    # Hold the singleton row lock until provisioning commits, serializing capacity checks.
    admitted = db.scalar(
        insert.values(id=1, day_number=day, starts_used=1)
        .on_conflict_do_update(
            index_elements=["id"],
            set_={
                "day_number": case((newer_day, day), else_=DemoStartBudget.day_number),
                "starts_used": case((newer_day, 1), else_=DemoStartBudget.starts_used + 1),
            },
            where=or_(
                newer_day,
                and_(
                    DemoStartBudget.day_number == day,
                    DemoStartBudget.starts_used < settings.demo_starts_per_day,
                ),
            ),
        )
        .returning(DemoStartBudget.id)
    )
    if admitted is None:
        db.commit()
        raise DemoStartLimitError()
    retained = db.scalar(select(func.count()).select_from(DemoWorkspace)) or 0
    if retained >= settings.demo_retained_workspaces:
        db.commit()  # Rejected starts still consume the daily admission.
        raise DemoStartLimitError()
    suffix = uuid4().hex
    workspace_id, department_id = "demo_" + suffix, "demo_dept_" + suffix
    manager_id, author_id = "demo_mgr_" + suffix, "demo_author_" + suffix
    department = Department(
        id=department_id, name="체험 조직 " + suffix, manager_employee_id=manager_id, is_active=True
    )
    db.add(department)
    db.flush()
    db.add(
        DemoWorkspace(
            id=workspace_id,
            department_id=department_id,
            expires_at_epoch=now + settings.demo_ttl_minutes * 60,
            write_limit=20,
            writes_used=0,
            request_limit=100,
            requests_used=0,
            is_active=True,
        )
    )
    db.flush()
    hire_date = date(2026, 1, 1)
    db.add(
        Employee(
            id=manager_id,
            name="체험 결재자",
            email=manager_id + "@jhworks.test",
            department_id=department_id,
            demo_workspace_id=workspace_id,
            position="팀장",
            role=EmployeeRole.MANAGER,
            hire_date=hire_date,
            leave_balance=Decimal("15.0"),
            is_active=True,
        )
    )
    db.flush()
    db.add(
        Employee(
            id=author_id,
            name="체험 작성자",
            email=author_id + "@jhworks.test",
            department_id=department_id,
            demo_workspace_id=workspace_id,
            manager_id=manager_id,
            position="팀원",
            role=EmployeeRole.EMPLOYEE,
            hire_date=hire_date,
            leave_balance=Decimal("15.0"),
            is_active=True,
        )
    )
    db.flush()
    year = datetime.fromtimestamp(now, UTC).year
    for employee_id in [author_id, manager_id]:
        db.add(
            LeaveAccount(
                id="demo_leave_" + uuid4().hex,
                employee_id=employee_id,
                year=year,
                granted_days=Decimal("15.0"),
            )
        )
    db.commit()
    return _load_actor(db, author_id)


def start_visit_safely(db: Session, settings: Settings, token: str | None) -> Employee:
    try:
        return start_visit(db, settings, token)
    except SQLAlchemyError:
        db.rollback()
        raise ServiceUnavailableError(
            "DEMO_START_UNAVAILABLE", "Demo provisioning is temporarily unavailable."
        ) from None


def switch_role(db: Session, actor: Employee, role: str) -> Employee:
    if actor.demo_workspace_id is None:
        raise AuthenticationError()
    expected = EmployeeRole.EMPLOYEE if role == "author" else EmployeeRole.MANAGER
    target = db.scalars(
        select(Employee).where(
            Employee.demo_workspace_id == actor.demo_workspace_id,
            Employee.role == expected,
            Employee.is_active.is_(True),
        )
    ).one_or_none()
    if target is None:
        raise AuthenticationError("The demo role is unavailable")
    require_demo_workspace(db, target)
    return target

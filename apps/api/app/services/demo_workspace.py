"""Request admission for server-managed demo employees; no public provisioning."""

from sqlalchemy import BigInteger, and_, cast, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import AppError, AuthenticationError, ServiceUnavailableError
from app.models.demo_workspace import DemoWorkspace
from app.models.employee import Employee


class DemoRequestLimitError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "DEMO_REQUEST_LIMIT_REACHED", "This demo workspace has reached its request limit.", 429
        )


class DemoWriteLimitError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "DEMO_WRITE_LIMIT_REACHED",
            "This demo workspace has reached its write limit.",
            429,
        )


def _database_epoch(db: Session) -> ColumnElement[int]:
    if db.get_bind().dialect.name == "postgresql":
        return cast(func.floor(func.extract("epoch", func.clock_timestamp())), BigInteger)
    if db.get_bind().dialect.name == "sqlite":
        return cast(func.strftime("%s", "now"), BigInteger)
    raise ValueError("Unsupported demo workspace database")


def require_demo_workspace(
    db: Session, actor: Employee, *, write: bool = False, admit: bool = True
) -> None:
    """Check persisted identity, then commit only the admission counter before business work."""
    if actor.demo_workspace_id is None:
        return
    if db.new or db.dirty or db.deleted:
        raise ValueError("Workspace admission must precede business changes")
    try:
        workspace = db.scalar(
            select(DemoWorkspace).where(
                DemoWorkspace.id == actor.demo_workspace_id,
                DemoWorkspace.is_active.is_(True),
                DemoWorkspace.expires_at_epoch > _database_epoch(db),
            )
        )
        if workspace is None:
            raise AuthenticationError("The demo workspace is unavailable or expired")
        if (
            actor.department_id != workspace.department_id
            or not actor.department.is_active
            or actor.department.parent_department_id is not None
        ):
            raise AuthenticationError("The demo workspace membership is invalid")
        outsider = db.scalar(
            select(Employee.id)
            .where(
                Employee.department_id == workspace.department_id,
                or_(
                    Employee.demo_workspace_id.is_(None), Employee.demo_workspace_id != workspace.id
                ),
            )
            .limit(1)
        )
        if outsider is not None:
            raise AuthenticationError("The demo department contains another workspace")
        related_ids = {actor.manager_id, actor.department.manager_employee_id} - {None}
        if related_ids:
            related = list(db.scalars(select(Employee).where(Employee.id.in_(related_ids))))
            if len(related) != len(related_ids) or any(
                item.demo_workspace_id != workspace.id
                or item.department_id != workspace.department_id
                or not item.is_active
                for item in related
            ):
                raise AuthenticationError("The demo workspace manager is unavailable")
        if not admit:
            return  # Feedback has its own one-per-workspace and global storage admission.
        # Evaluate DB time inside UPDATE as well: a lock wait must not admit an expired space.
        admitted = db.scalar(
            update(DemoWorkspace)
            .where(
                DemoWorkspace.id == workspace.id,
                DemoWorkspace.is_active.is_(True),
                DemoWorkspace.expires_at_epoch > _database_epoch(db),
                DemoWorkspace.requests_used < DemoWorkspace.request_limit,
                (DemoWorkspace.writes_used < DemoWorkspace.write_limit) if write else and_(True),
            )
            .values(
                writes_used=DemoWorkspace.writes_used + (1 if write else 0),
                requests_used=DemoWorkspace.requests_used + 1,
            )
            .returning(DemoWorkspace.id)
            .execution_options(synchronize_session=False)
        )
        db.commit()
        if admitted is None:
            active = db.scalar(
                select(DemoWorkspace.id).where(
                    DemoWorkspace.id == actor.demo_workspace_id,
                    DemoWorkspace.is_active.is_(True),
                    DemoWorkspace.expires_at_epoch > _database_epoch(db),
                )
            )
            if active is None:
                raise AuthenticationError("The demo workspace is unavailable or expired")
            current = db.get(DemoWorkspace, actor.demo_workspace_id, populate_existing=True)
            if current is not None and current.requests_used >= current.request_limit:
                raise DemoRequestLimitError()
            raise DemoWriteLimitError()
    except SQLAlchemyError:
        db.rollback()
        raise ServiceUnavailableError(
            "DEMO_WORKSPACE_UNAVAILABLE", "The demo workspace is temporarily unavailable."
        ) from None

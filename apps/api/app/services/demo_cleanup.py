"""Bounded expiry cleanup; never converts a guest into a private employee."""

from dataclasses import dataclass

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models.approval import Approval, ApprovalLine
from app.models.attendance import LeaveAccount, WorkCalendarEvent
from app.models.demo_workspace import DemoWorkspace
from app.models.employee import Credential, Department, Employee
from app.models.leave_agent import LeaveAgentRun
from app.services.login_budget import database_seconds


@dataclass(frozen=True)
class DemoCleanupResult:
    planned: int
    removed: int


def _refuse() -> None:
    raise ConflictError("DEMO_CLEANUP_UNSAFE", "Demo cleanup found an unexpected relationship.")


def _owned_graph(db: Session, workspace: DemoWorkspace) -> tuple[list[str], list[str]]:
    suffix = workspace.id.removeprefix("demo_")
    if (
        not workspace.id.startswith("demo_")
        or len(suffix) != 32
        or workspace.department_id != "demo_dept_" + suffix
    ):
        _refuse()
    employees = list(
        db.scalars(
            select(Employee)
            .where(
                Employee.demo_workspace_id == workspace.id,
            )
            .limit(3)
        )
    )
    ids = [item.id for item in employees]
    if set(ids) != {"demo_author_" + suffix, "demo_mgr_" + suffix} or any(
        item.department_id != workspace.department_id
        or (item.manager_id is not None and item.manager_id not in ids)
        for item in employees
    ):
        _refuse()
    if db.scalar(select(Credential.employee_id).where(Credential.employee_id.in_(ids)).limit(1)):
        _refuse()
    if db.scalar(
        select(Employee.id)
        .where(
            Employee.id.not_in(ids),
            or_(Employee.department_id == workspace.department_id, Employee.manager_id.in_(ids)),
        )
        .limit(1)
    ):
        _refuse()
    department = db.get(Department, workspace.department_id)
    if (
        department is None
        or department.parent_department_id is not None
        or department.manager_employee_id not in ids
    ):
        _refuse()
    if db.scalar(
        select(Department.id)
        .where(
            Department.id != workspace.department_id,
            or_(
                Department.parent_department_id == workspace.department_id,
                Department.manager_employee_id.in_(ids),
            ),
        )
        .limit(1)
    ):
        _refuse()
    approvals = list(db.scalars(select(Approval.id).where(Approval.author_id.in_(ids)).limit(201)))
    if len(approvals) > 200:
        _refuse()
    if db.scalar(
        select(ApprovalLine.id)
        .where(
            or_(
                (ApprovalLine.approval_id.in_(approvals) & ApprovalLine.approver_id.not_in(ids)),
                (ApprovalLine.approver_id.in_(ids) & ApprovalLine.approval_id.not_in(approvals)),
            )
        )
        .limit(1)
    ):
        _refuse()
    events = list(
        db.scalars(
            select(WorkCalendarEvent)
            .where(
                or_(
                    WorkCalendarEvent.employee_id.in_(ids),
                    WorkCalendarEvent.department_id == workspace.department_id,
                    WorkCalendarEvent.approval_id.in_(approvals),
                )
            )
            .limit(501)
        )
    )
    if len(events) > 500 or any(
        (item.employee_id is not None and item.employee_id not in ids)
        or (item.department_id is not None and item.department_id != workspace.department_id)
        or (item.approval_id is not None and item.approval_id not in approvals)
        for item in events
    ):
        _refuse()
    if db.scalar(
        select(LeaveAgentRun.id)
        .where(
            or_(
                (LeaveAgentRun.actor_id.in_(ids) & LeaveAgentRun.approval_id.not_in(approvals)),
                (LeaveAgentRun.approval_id.in_(approvals) & LeaveAgentRun.actor_id.not_in(ids)),
            )
        )
        .limit(1)
    ):
        _refuse()
    for statement, limit in [
        (select(ApprovalLine.id).where(ApprovalLine.approval_id.in_(approvals)), 500),
        (select(LeaveAgentRun.id).where(LeaveAgentRun.actor_id.in_(ids)), 200),
        (select(LeaveAccount.id).where(LeaveAccount.employee_id.in_(ids)), 10),
    ]:
        if len(list(db.scalars(statement.limit(limit + 1)))) > limit:
            _refuse()
    return ids, approvals


def cleanup_expired_demo(
    db: Session,
    *,
    apply: bool = False,
    batch_size: int = 5,
    retention_seconds: int = 86400,
) -> DemoCleanupResult:
    if not 1 <= batch_size <= 10 or retention_seconds < 86400:
        raise ValueError("Cleanup requires a 1..10 batch and at least 24h expired retention")
    if db.new or db.dirty or db.deleted or db.in_transaction():
        raise ValueError("Cleanup requires a fresh session")
    try:
        cutoff = database_seconds(db) - retention_seconds
        workspaces = list(
            db.scalars(
                select(DemoWorkspace)
                .where(
                    DemoWorkspace.expires_at_epoch <= cutoff,
                )
                .order_by(DemoWorkspace.expires_at_epoch, DemoWorkspace.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        for workspace in workspaces:
            employees, approvals = _owned_graph(db, workspace)
            if not apply:
                continue
            db.execute(
                update(DemoWorkspace)
                .where(DemoWorkspace.id == workspace.id)
                .values(is_active=False)
            )
            db.execute(delete(LeaveAgentRun).where(LeaveAgentRun.actor_id.in_(employees)))
            db.execute(
                delete(WorkCalendarEvent).where(
                    or_(
                        WorkCalendarEvent.employee_id.in_(employees),
                        WorkCalendarEvent.department_id == workspace.department_id,
                        WorkCalendarEvent.approval_id.in_(approvals),
                    )
                )
            )
            db.execute(delete(ApprovalLine).where(ApprovalLine.approval_id.in_(approvals)))
            db.execute(delete(Approval).where(Approval.id.in_(approvals)))
            db.execute(delete(LeaveAccount).where(LeaveAccount.employee_id.in_(employees)))
            db.execute(update(Employee).where(Employee.id.in_(employees)).values(manager_id=None))
            db.execute(delete(Employee).where(Employee.id.in_(employees)))
            db.execute(delete(DemoWorkspace).where(DemoWorkspace.id == workspace.id))
            db.execute(delete(Department).where(Department.id == workspace.department_id))
        result = DemoCleanupResult(planned=len(workspaces), removed=len(workspaces) if apply else 0)
        if apply:
            db.commit()
        else:
            db.rollback()
        return result
    except Exception:
        db.rollback()
        raise

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.errors import (
    AuthorizationError,
    ConflictError,
    DomainValidationError,
    NotFoundError,
)
from app.models.approval import Approval, ApprovalLine
from app.models.attendance import LeaveAccount, WorkCalendarEvent
from app.models.employee import Employee
from app.models.enums import (
    ApprovalLineStatus,
    ApprovalStatus,
    ApprovalType,
    AttendanceEventCategory,
    AttendanceEventScope,
    AttendanceEventStatus,
    AttendanceImpact,
)
from app.schemas.approval import ApprovalCreate, ApprovalDecision, ApprovalUpdate
from app.services.leave_calendar import calculate_leave_days


def _approval_query() -> Select[tuple[Approval]]:
    return (
        select(Approval)
        .options(
            joinedload(Approval.author),
            selectinload(Approval.lines).joinedload(ApprovalLine.approver),
        )
        .execution_options(populate_existing=True)
    )


def _get_approval(db: Session, approval_id: str) -> Approval:
    approval = db.scalar(_approval_query().where(Approval.id == approval_id))
    if approval is None:
        raise NotFoundError("Approval")
    return approval


def _get_approval_for_update(db: Session, approval_id: str) -> Approval:
    locked = db.scalar(select(Approval.id).where(Approval.id == approval_id).with_for_update())
    if locked is None:
        raise NotFoundError("Approval")
    return _get_approval(db, approval_id)


def _can_view(approval: Approval, actor: Employee) -> bool:
    return approval.author_id == actor.id or any(
        line.approver_id == actor.id for line in approval.lines
    )


def _require_author(approval: Approval, actor: Employee) -> None:
    if approval.author_id != actor.id:
        raise AuthorizationError("Only the approval author can perform this action")


def _require_version(approval: Approval, expected_version: int) -> None:
    if approval.version != expected_version:
        raise ConflictError(
            "VERSION_CONFLICT",
            "The approval changed after it was loaded. Refresh and try again.",
        )


def _current_line(approval: Approval) -> ApprovalLine:
    pending = [line for line in approval.lines if line.status == ApprovalLineStatus.PENDING]
    if len(pending) != 1:
        raise ConflictError("INVALID_APPROVAL_LINE", "The approval has no single pending line")
    return pending[0]


def _parse_detail_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _normalized_details(
    db: Session,
    employee: Employee,
    approval_type: ApprovalType,
    details: dict[str, object],
) -> dict[str, object]:
    if approval_type != ApprovalType.LEAVE:
        return details

    normalized = details.copy()
    start_date = _parse_detail_date(normalized.get("startDate"))
    end_date = _parse_detail_date(normalized.get("endDate"))
    leave_unit = normalized.get("leaveUnit")
    calculated = None
    if start_date is not None and end_date is not None and isinstance(leave_unit, str):
        calculated = calculate_leave_days(db, employee, start_date, end_date, leave_unit)
    normalized["requestedDays"] = str(calculated) if calculated is not None else None
    return normalized


def _validate_for_submit(db: Session, approval: Approval) -> None:
    errors: dict[str, str] = {}
    if not approval.title.strip():
        errors["title"] = "Title is required"
    if not approval.content.strip():
        errors["content"] = "Content is required"

    if approval.type == ApprovalType.BUSINESS_TRIP:
        details = approval.details
        required_fields = ("destination", "startDate", "endDate", "clientName", "visitPurpose")
        for field in required_fields:
            value = details.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors[f"details.{field}"] = "This field is required for a business trip"

        start_date = details.get("startDate")
        end_date = details.get("endDate")
        if start_date and end_date and start_date > end_date:
            errors["details.endDate"] = "End date must be on or after start date"
        if approval.amount is None:
            errors["amount"] = "Estimated amount is required for a business trip"

    if approval.type == ApprovalType.LEAVE:
        details = approval.details
        start_date = _parse_detail_date(details.get("startDate"))
        end_date = _parse_detail_date(details.get("endDate"))
        leave_unit = details.get("leaveUnit")
        if start_date is None:
            errors["details.startDate"] = "Start date is required for leave"
        if end_date is None:
            errors["details.endDate"] = "End date is required for leave"
        if start_date is not None and end_date is not None:
            if start_date > end_date:
                errors["details.endDate"] = "End date must be on or after start date"
            elif start_date.year != end_date.year:
                errors["details.endDate"] = "Leave must start and end in the same year"
            elif isinstance(leave_unit, str):
                requested_days = calculate_leave_days(
                    db, approval.author, start_date, end_date, leave_unit
                )
                if requested_days is None:
                    errors["details.leaveUnit"] = (
                        "The selected dates do not contain a valid leave workday"
                    )
                elif Decimal(str(details.get("requestedDays"))) != requested_days:
                    errors["details.requestedDays"] = "Requested days must match the work calendar"

    if errors:
        raise DomainValidationError(
            "APPROVAL_NOT_READY",
            "The approval is missing information required for submission",
            errors,
        )


def create_draft(
    db: Session,
    actor: Employee,
    payload: ApprovalCreate,
    source_confirmation_id: str | None = None,
) -> Approval:
    if not actor.is_active:
        raise AuthorizationError("Inactive employees cannot create approvals")

    if source_confirmation_id is not None:
        existing = db.scalar(
            select(Approval).where(
                Approval.source_confirmation_id == source_confirmation_id,
                Approval.author_id == actor.id,
            )
        )
        if existing is not None:
            return _get_approval(db, existing.id)

    approval = Approval(
        id=f"apr_{uuid4().hex}",
        type=payload.type,
        title=payload.title.strip(),
        content=payload.content.strip(),
        author_id=actor.id,
        status=ApprovalStatus.DRAFT,
        amount=payload.amount,
        details=payload.details.model_dump(mode="json", by_alias=True),
        attachment_metadata=[
            item.model_dump(mode="json", by_alias=True) for item in payload.attachment_metadata
        ],
        source_confirmation_id=source_confirmation_id,
    )
    approval.details = _normalized_details(
        db,
        actor,
        payload.type,
        approval.details,
    )
    db.add(approval)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if source_confirmation_id is None:
            raise
        existing = db.scalar(
            select(Approval).where(
                Approval.source_confirmation_id == source_confirmation_id,
                Approval.author_id == actor.id,
            )
        )
        if existing is None:
            raise
        return _get_approval(db, existing.id)
    return _get_approval(db, approval.id)


def list_approvals(db: Session, actor: Employee, scope: str) -> list[Approval]:
    query = _approval_query().order_by(Approval.updated_at.desc())
    if scope == "mine":
        query = query.where(Approval.author_id == actor.id)
    elif scope == "assigned":
        query = query.join(ApprovalLine).where(ApprovalLine.approver_id == actor.id).distinct()
    else:
        raise DomainValidationError("INVALID_SCOPE", "scope must be 'mine' or 'assigned'")
    return list(db.scalars(query).unique())


def get_approval(db: Session, actor: Employee, approval_id: str) -> Approval:
    approval = _get_approval(db, approval_id)
    if not _can_view(approval, actor):
        raise AuthorizationError("You cannot view this approval")
    return approval


def update_draft(
    db: Session,
    actor: Employee,
    approval_id: str,
    payload: ApprovalUpdate,
) -> Approval:
    approval = _get_approval_for_update(db, approval_id)
    _require_author(approval, actor)
    _require_version(approval, payload.version)
    if approval.status != ApprovalStatus.DRAFT:
        raise ConflictError("INVALID_STATUS", "Only draft approvals can be edited")

    approval.type = payload.type
    approval.title = payload.title.strip()
    approval.content = payload.content.strip()
    approval.amount = payload.amount
    approval.details = _normalized_details(
        db,
        actor,
        payload.type,
        payload.details.model_dump(mode="json", by_alias=True),
    )
    approval.attachment_metadata = [
        item.model_dump(mode="json", by_alias=True) for item in payload.attachment_metadata
    ]
    approval.version += 1
    approval.updated_at = datetime.now(UTC)
    db.commit()
    return _get_approval(db, approval.id)


def submit_approval(
    db: Session,
    actor: Employee,
    approval_id: str,
    expected_version: int,
) -> Approval:
    approval = _get_approval_for_update(db, approval_id)
    _require_author(approval, actor)
    _require_version(approval, expected_version)
    if approval.status != ApprovalStatus.DRAFT:
        raise ConflictError("INVALID_STATUS", "Only draft approvals can be submitted")
    approval.details = _normalized_details(db, actor, approval.type, approval.details)
    _validate_for_submit(db, approval)

    manager = db.get(Employee, actor.manager_id) if actor.manager_id else None
    if manager is None or not manager.is_active or manager.id == actor.id:
        raise ConflictError("MANAGER_UNAVAILABLE", "An active manager is required for submission")

    if approval.type == ApprovalType.LEAVE:
        _reserve_leave(db, approval)

    current_round = db.scalar(
        select(func.max(ApprovalLine.round)).where(ApprovalLine.approval_id == approval.id)
    )
    line = ApprovalLine(
        id=f"line_{uuid4().hex}",
        approval_id=approval.id,
        step=1,
        round=(current_round or 0) + 1,
        approver_id=manager.id,
        status=ApprovalLineStatus.PENDING,
    )
    now = datetime.now(UTC)
    approval.status = ApprovalStatus.PENDING
    approval.submitted_at = now
    approval.decided_at = None
    approval.version += 1
    approval.updated_at = now
    db.add(line)
    db.commit()
    return _get_approval(db, approval.id)


def decide_approval(
    db: Session,
    actor: Employee,
    approval_id: str,
    payload: ApprovalDecision,
    decision: ApprovalStatus,
) -> Approval:
    approval = _get_approval_for_update(db, approval_id)
    _require_version(approval, payload.version)
    if approval.status != ApprovalStatus.PENDING:
        raise ConflictError("INVALID_STATUS", "Only pending approvals can be decided")

    line = _current_line(approval)
    if line.approver_id != actor.id:
        raise AuthorizationError("Only the assigned approver can decide this approval")
    if decision == ApprovalStatus.REJECTED and not (payload.comment or "").strip():
        raise DomainValidationError("COMMENT_REQUIRED", "A rejection comment is required")

    now = datetime.now(UTC)
    line.status = (
        ApprovalLineStatus.APPROVED
        if decision == ApprovalStatus.APPROVED
        else ApprovalLineStatus.REJECTED
    )
    line.comment = (payload.comment or "").strip() or None
    line.acted_at = now
    approval.status = decision
    approval.decided_at = now
    approval.version += 1
    approval.updated_at = now
    if approval.type == ApprovalType.LEAVE:
        _finalize_leave(db, approval, decision)
    db.commit()
    return _get_approval(db, approval.id)


def _leave_request_values(approval: Approval) -> tuple[date, date, Decimal]:
    start_date = _parse_detail_date(approval.details.get("startDate"))
    end_date = _parse_detail_date(approval.details.get("endDate"))
    requested_value = approval.details.get("requestedDays")
    if start_date is None or end_date is None or requested_value is None:
        raise ConflictError("INVALID_LEAVE_REQUEST", "The leave request is incomplete")
    return start_date, end_date, Decimal(str(requested_value))


def _locked_leave_account(db: Session, employee_id: str, year: int) -> LeaveAccount:
    account = db.scalar(
        select(LeaveAccount)
        .where(LeaveAccount.employee_id == employee_id, LeaveAccount.year == year)
        .with_for_update()
    )
    if account is None:
        raise ConflictError(
            "LEAVE_ACCOUNT_UNAVAILABLE",
            f"No leave account is available for {year}",
        )
    return account


def _reserve_leave(db: Session, approval: Approval) -> None:
    start_date, end_date, requested_days = _leave_request_values(approval)
    account = _locked_leave_account(db, approval.author_id, start_date.year)
    if account.available_days < requested_days:
        raise DomainValidationError(
            "INSUFFICIENT_LEAVE_BALANCE",
            "The requested leave exceeds the available balance",
            {
                "requestedDays": str(requested_days),
                "availableDays": str(account.available_days),
            },
        )

    event = db.scalar(
        select(WorkCalendarEvent)
        .where(WorkCalendarEvent.approval_id == approval.id)
        .with_for_update()
    )
    if event is None:
        event = WorkCalendarEvent(
            id=f"cal_{uuid4().hex}",
            approval_id=approval.id,
            category=AttendanceEventCategory.LEAVE,
            title="연차",
            start_date=start_date,
            end_date=end_date,
            scope=AttendanceEventScope.EMPLOYEE,
            employee_id=approval.author_id,
            status=AttendanceEventStatus.TENTATIVE,
            impact=AttendanceImpact.CAUTION,
        )
        db.add(event)
    else:
        event.start_date = start_date
        event.end_date = end_date
        event.employee_id = approval.author_id
        event.status = AttendanceEventStatus.TENTATIVE

    account.pending_days += requested_days
    account.version += 1


def _finalize_leave(db: Session, approval: Approval, decision: ApprovalStatus) -> None:
    start_date, _, requested_days = _leave_request_values(approval)
    account = _locked_leave_account(db, approval.author_id, start_date.year)
    event = db.scalar(
        select(WorkCalendarEvent)
        .where(WorkCalendarEvent.approval_id == approval.id)
        .with_for_update()
    )
    if event is None or event.status != AttendanceEventStatus.TENTATIVE:
        raise ConflictError(
            "LEAVE_RESERVATION_INCONSISTENT",
            "The leave calendar reservation is missing or invalid",
        )
    if account.pending_days < requested_days:
        raise ConflictError(
            "LEAVE_RESERVATION_INCONSISTENT",
            "The pending leave balance is smaller than the request",
        )

    account.pending_days -= requested_days
    account.version += 1
    if decision == ApprovalStatus.APPROVED:
        account.used_days += requested_days
        event.status = AttendanceEventStatus.CONFIRMED
    else:
        event.status = AttendanceEventStatus.CANCELED


def revise_approval(
    db: Session,
    actor: Employee,
    approval_id: str,
    expected_version: int,
) -> Approval:
    approval = _get_approval_for_update(db, approval_id)
    _require_author(approval, actor)
    _require_version(approval, expected_version)
    if approval.status != ApprovalStatus.REJECTED:
        raise ConflictError("INVALID_STATUS", "Only rejected approvals can return to draft")

    approval.status = ApprovalStatus.DRAFT
    approval.submitted_at = None
    approval.decided_at = None
    approval.version += 1
    approval.updated_at = datetime.now(UTC)
    db.commit()
    return _get_approval(db, approval.id)

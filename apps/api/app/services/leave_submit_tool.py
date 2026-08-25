import hashlib
import hmac
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AuthorizationError, ConflictError
from app.core.security import (
    LeaveSubmitConfirmation,
    create_leave_submit_confirmation_token,
    decode_leave_submit_confirmation_token,
)
from app.models.approval import Approval
from app.models.attendance import LeaveAccount
from app.models.employee import Employee
from app.models.enums import ApprovalStatus, ApprovalType, AttendanceImpact
from app.schemas.leave_agent import LeaveSubmitPreview
from app.services import approval as approval_service
from app.services import leave_availability
from app.services.approval import ConfirmedLeaveSubmitSnapshot
from app.services.leave_calendar import calculate_leave_days, leave_calendar_fingerprint


def preview_hash(preview: LeaveSubmitPreview) -> str:
    encoded = json.dumps(
        preview.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _parse_date(value: object) -> date:
    if not isinstance(value, str):
        raise ConflictError("INVALID_LEAVE_REQUEST", "The leave request dates are incomplete.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConflictError(
            "INVALID_LEAVE_REQUEST",
            "The leave request dates are invalid.",
        ) from exc


def _draft_for_submit(
    db: Session,
    actor: Employee,
    approval_id: str,
    expected_version: int,
) -> Approval:
    approval = approval_service.get_approval(db, actor, approval_id)
    if approval.author_id != actor.id:
        raise AuthorizationError("Only the leave author can submit this draft")
    if approval.type != ApprovalType.LEAVE:
        raise ConflictError("INVALID_LEAVE_REQUEST", "Only a leave draft can use this tool.")
    if approval.status != ApprovalStatus.DRAFT:
        raise ConflictError("INVALID_STATUS", "Only a draft can be prepared for submission.")
    if approval.version != expected_version:
        raise ConflictError(
            "VERSION_CONFLICT",
            "The approval changed after it was loaded. Refresh and try again.",
        )
    return approval


def _account(db: Session, actor: Employee, year: int) -> LeaveAccount:
    account = db.scalar(
        select(LeaveAccount).where(
            LeaveAccount.employee_id == actor.id,
            LeaveAccount.year == year,
        )
    )
    if account is None:
        raise ConflictError(
            "LEAVE_ACCOUNT_UNAVAILABLE",
            f"No leave account is available for {year}",
        )
    return account


def _manager(db: Session, actor: Employee) -> Employee:
    manager = db.get(Employee, actor.manager_id) if actor.manager_id else None
    if manager is None or not manager.is_active or manager.id == actor.id:
        raise ConflictError("MANAGER_UNAVAILABLE", "An active manager is required for submission")
    return manager


def build_submit_preview(
    db: Session,
    actor: Employee,
    approval_id: str,
    expected_version: int,
) -> LeaveSubmitPreview:
    approval = _draft_for_submit(db, actor, approval_id, expected_version)
    start_date = _parse_date(approval.details.get("startDate"))
    end_date = _parse_date(approval.details.get("endDate"))
    leave_unit = approval.details.get("leaveUnit")
    if not isinstance(leave_unit, str):
        raise ConflictError("INVALID_LEAVE_REQUEST", "The leave unit is missing.")
    requested_days = calculate_leave_days(db, actor, start_date, end_date, leave_unit)
    stored_requested_days = approval.details.get("requestedDays")
    if requested_days is None or Decimal(str(stored_requested_days)) != requested_days:
        raise ConflictError(
            "INVALID_LEAVE_REQUEST",
            "The leave deduction no longer matches the work calendar.",
        )
    account = _account(db, actor, start_date.year)
    if account.available_days < requested_days:
        raise ConflictError(
            "LEAVE_SUBMIT_STALE",
            "The current available balance is smaller than the leave request.",
        )
    availability = leave_availability.find_leave_availability(
        db,
        actor,
        start_date,
        end_date,
        requested_days,
        limit=10,
    )
    candidate = next(
        (
            item
            for item in availability.candidates
            if item.start_date == start_date
            and item.end_date == end_date
            and item.requested_days == requested_days
        ),
        None,
    )
    if candidate is None:
        raise ConflictError(
            "LEAVE_SUBMIT_STALE",
            "The leave dates are no longer available. Return to leave consultation.",
        )
    manager = _manager(db, actor)
    return LeaveSubmitPreview(
        approval_id=approval.id,
        approval_version=approval.version,
        requested_days=requested_days,
        available_days=account.available_days,
        pending_days=account.pending_days,
        account_version=account.version,
        manager_id=manager.id,
        manager_name=manager.name,
        manager_position=manager.position,
        warnings=[
            reason for reason in candidate.reasons if reason.impact == AttendanceImpact.CAUTION
        ],
        calendar_fingerprint=leave_calendar_fingerprint(
            db,
            actor,
            start_date,
            end_date,
        ),
    )


def create_submit_confirmation(
    actor: Employee,
    run_id: str,
    preview: LeaveSubmitPreview,
) -> tuple[str, str, datetime]:
    settings = get_settings()
    confirmation_id = f"submit_confirm_{uuid4().hex}"
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.leave_submit_confirmation_ttl_minutes
    )
    token = create_leave_submit_confirmation_token(
        employee_id=actor.id,
        confirmation_id=confirmation_id,
        run_id=run_id,
        approval_id=preview.approval_id,
        preview_hash=preview_hash(preview),
        approval_version=preview.approval_version,
        account_version=preview.account_version,
        calendar_fingerprint=preview.calendar_fingerprint,
        manager_id=preview.manager_id,
        expires_at=expires_at,
    )
    return token, confirmation_id, expires_at


def validate_submit_confirmation(
    db: Session,
    actor: Employee,
    run_id: str,
    preview: LeaveSubmitPreview,
    token: str,
) -> tuple[Approval, ConfirmedLeaveSubmitSnapshot, LeaveSubmitConfirmation]:
    confirmation = validate_submit_token_identity(actor, run_id, preview, token)

    approval = _draft_for_submit(
        db,
        actor,
        preview.approval_id,
        preview.approval_version,
    )
    current = build_submit_preview(
        db,
        actor,
        preview.approval_id,
        preview.approval_version,
    )
    if (
        confirmation.approval_version != current.approval_version
        or confirmation.account_version != current.account_version
        or confirmation.manager_id != current.manager_id
        or not hmac.compare_digest(
            confirmation.calendar_fingerprint,
            current.calendar_fingerprint,
        )
        or not hmac.compare_digest(preview_hash(current), preview_hash(preview))
    ):
        raise ConflictError(
            "LEAVE_SUBMIT_STALE",
            "The leave submission inputs changed after preview.",
        )
    return (
        approval,
        ConfirmedLeaveSubmitSnapshot(
            manager_id=current.manager_id,
            account_version=current.account_version,
            calendar_fingerprint=current.calendar_fingerprint,
        ),
        confirmation,
    )


def validate_submit_token_identity(
    actor: Employee,
    run_id: str,
    preview: LeaveSubmitPreview,
    token: str,
) -> LeaveSubmitConfirmation:
    confirmation = decode_leave_submit_confirmation_token(token)
    if confirmation.employee_id != actor.id:
        raise AuthorizationError("This leave submission confirmation belongs to another employee")
    if confirmation.run_id != run_id:
        raise AuthorizationError("This confirmation belongs to another leave workflow")
    if (
        confirmation.approval_id != preview.approval_id
        or not hmac.compare_digest(confirmation.preview_hash, preview_hash(preview))
    ):
        raise ConflictError(
            "LEAVE_SUBMIT_PREVIEW_CHANGED",
            "The submission preview changed after it was prepared.",
        )
    return confirmation


def execute_confirmed_submit(
    db: Session,
    actor: Employee,
    approval: Approval,
    snapshot: ConfirmedLeaveSubmitSnapshot,
) -> Approval:
    return approval_service.submit_approval(
        db,
        actor,
        approval.id,
        approval.version,
        leave_confirmation=snapshot,
    )

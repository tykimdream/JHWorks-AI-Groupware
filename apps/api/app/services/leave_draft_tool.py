import hashlib
import hmac
import json
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.policy_embedding import PolicyEmbeddingProvider
from app.core.config import get_settings
from app.core.errors import (
    AuthorizationError,
    ConflictError,
    DomainValidationError,
    ServiceUnavailableError,
)
from app.core.security import (
    create_leave_draft_confirmation_token,
    decode_leave_draft_confirmation_token,
)
from app.models.approval import Approval
from app.models.attendance import LeaveAccount
from app.models.employee import Employee
from app.models.enums import ApprovalType, AttendanceImpact, PolicyType
from app.schemas.approval import ApprovalCreate, LeaveDetails
from app.schemas.attendance import LeaveAvailabilityCandidateRead
from app.schemas.leave_draft_tool import (
    LeaveDraftApproverRead,
    LeaveDraftExactPreview,
    LeaveDraftPrepareRequest,
    LeaveDraftPrepareResponse,
)
from app.schemas.policy import PolicyRetrievalStatus, PolicySearchResponse
from app.services import approval as approval_service
from app.services import leave_availability, policy_retrieval
from app.services.leave_calendar import calculate_leave_days, leave_calendar_fingerprint


def _canonical_hash(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", by_alias=True)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _manager(db: Session, actor: Employee) -> Employee:
    manager = db.get(Employee, actor.manager_id) if actor.manager_id else None
    if manager is None or not manager.is_active or manager.id == actor.id:
        raise ConflictError(
            "MANAGER_UNAVAILABLE",
            "An active manager is required for a leave draft preview.",
        )
    return manager


def _leave_account(
    db: Session,
    actor: Employee,
    year: int,
    *,
    lock: bool = False,
) -> LeaveAccount:
    statement = select(LeaveAccount).where(
        LeaveAccount.employee_id == actor.id,
        LeaveAccount.year == year,
    )
    if lock:
        statement = statement.with_for_update()
    account = db.scalar(statement)
    if account is None:
        raise ConflictError(
            "LEAVE_ACCOUNT_UNAVAILABLE",
            f"No leave account is available for {year}",
        )
    return account


def _policy_context(
    db: Session,
    candidate: LeaveAvailabilityCandidateRead,
    provider: PolicyEmbeddingProvider,
) -> PolicySearchResponse:
    settings = get_settings()
    query = (
        "JHWorks annual leave draft, balance deduction, approval, and notice policy. "
        f"Leave dates: {candidate.start_date} through {candidate.end_date}. "
        f"Requested leave: {candidate.requested_days} days."
    )
    result = policy_retrieval.search_policy_sections(
        db=db,
        query=query,
        policy_type=PolicyType.LEAVE,
        top_k=settings.policy_retrieval_top_k,
        min_score=settings.policy_retrieval_min_score,
        provider=provider,
        expected_model=settings.policy_embedding_model,
        expected_dimensions=settings.policy_embedding_dimensions,
    )
    if result.status != PolicyRetrievalStatus.READY or not result.items:
        raise ServiceUnavailableError(
            "LEAVE_POLICY_UNAVAILABLE",
            "Active leave policy evidence is required before preparing a draft.",
        )
    return result


def _validated_candidate(
    db: Session,
    actor: Employee,
    candidate: LeaveAvailabilityCandidateRead,
) -> LeaveAvailabilityCandidateRead:
    availability = leave_availability.find_leave_availability(
        db,
        actor,
        candidate.start_date,
        candidate.end_date,
        candidate.requested_days,
        limit=10,
    )
    expected_hash = _canonical_hash(candidate)
    canonical = next(
        (item for item in availability.candidates if _canonical_hash(item) == expected_hash),
        None,
    )
    if canonical is None:
        raise ConflictError(
            "LEAVE_CANDIDATE_STALE",
            "The selected leave candidate is no longer available. Search again.",
        )
    return canonical


def _validate_unit(requested_days: Decimal, leave_unit: str) -> None:
    if requested_days == Decimal("0.5"):
        if leave_unit not in {"HALF_DAY_AM", "HALF_DAY_PM"}:
            raise DomainValidationError(
                "INVALID_LEAVE_UNIT",
                "A half-day candidate requires a morning or afternoon unit.",
            )
    elif leave_unit != "FULL_DAY":
        raise DomainValidationError(
            "INVALID_LEAVE_UNIT",
            "A whole-day candidate requires the full-day unit.",
        )


def _approval_preview(
    candidate: LeaveAvailabilityCandidateRead,
    leave_unit: str,
) -> ApprovalCreate:
    date_label = candidate.start_date.isoformat()
    if candidate.start_date != candidate.end_date:
        date_label += f" ~ {candidate.end_date.isoformat()}"
    return ApprovalCreate(
        type=ApprovalType.LEAVE,
        title=f"{date_label} 연차 신청",
        content=f"{candidate.requested_days}일 연차 사용을 신청합니다.",
        amount=None,
        details=LeaveDetails(
            leave_type="ANNUAL",
            leave_unit=leave_unit,
            start_date=candidate.start_date,
            end_date=candidate.end_date,
            requested_days=candidate.requested_days,
            reason=None,
            handover_note=None,
        ),
        attachment_metadata=[],
    )


def prepare_leave_draft(
    db: Session,
    actor: Employee,
    payload: LeaveDraftPrepareRequest,
    embedding_provider: PolicyEmbeddingProvider,
) -> LeaveDraftPrepareResponse:
    canonical_candidate = _validated_candidate(db, actor, payload.candidate)
    _validate_unit(canonical_candidate.requested_days, payload.leave_unit)
    account = _leave_account(db, actor, canonical_candidate.start_date.year)
    if account.available_days < canonical_candidate.requested_days:
        raise ConflictError(
            "LEAVE_CANDIDATE_STALE",
            "The available leave balance changed. Search again.",
        )
    manager = _manager(db, actor)
    policy_context = _policy_context(db, canonical_candidate, embedding_provider)
    calendar_fingerprint = leave_calendar_fingerprint(
        db,
        actor,
        canonical_candidate.start_date,
        canonical_candidate.end_date,
    )
    policy_fingerprint = policy_retrieval.active_policy_fingerprint(db, PolicyType.LEAVE)
    preview = LeaveDraftExactPreview(
        approval=_approval_preview(canonical_candidate, payload.leave_unit),
        candidate=canonical_candidate,
        requested_days=canonical_candidate.requested_days,
        leave_unit=payload.leave_unit,
        available_days=account.available_days,
        account_version=account.version,
        manager=LeaveDraftApproverRead(
            id=manager.id,
            name=manager.name,
            position=manager.position,
        ),
        policy_context=policy_context,
        warnings=[
            reason
            for reason in canonical_candidate.reasons
            if reason.impact == AttendanceImpact.CAUTION
        ],
        calendar_fingerprint=calendar_fingerprint,
        policy_fingerprint=policy_fingerprint,
    )
    confirmation_id = f"leave_confirm_{uuid4().hex}"
    token = create_leave_draft_confirmation_token(
        employee_id=actor.id,
        confirmation_id=confirmation_id,
        preview_hash=_canonical_hash(preview),
        candidate_hash=_canonical_hash(canonical_candidate),
        account_version=account.version,
        calendar_fingerprint=calendar_fingerprint,
        manager_id=manager.id,
        policy_fingerprint=policy_fingerprint,
    )
    return LeaveDraftPrepareResponse(preview=preview, confirmation_token=token)


def _validate_approval_matches_preview(
    db: Session,
    actor: Employee,
    preview: LeaveDraftExactPreview,
) -> None:
    approval = preview.approval
    if approval.type != ApprovalType.LEAVE or not isinstance(approval.details, LeaveDetails):
        raise ConflictError("LEAVE_PREVIEW_CHANGED", "The leave draft preview is invalid.")
    details = approval.details
    calculated = (
        calculate_leave_days(
            db,
            actor,
            preview.candidate.start_date,
            preview.candidate.end_date,
            preview.leave_unit,
        )
        if details.start_date is not None and details.end_date is not None
        else None
    )
    if (
        details.start_date != preview.candidate.start_date
        or details.end_date != preview.candidate.end_date
        or details.leave_unit != preview.leave_unit
        or details.requested_days != preview.requested_days
        or calculated != preview.requested_days
    ):
        raise ConflictError(
            "LEAVE_PREVIEW_CHANGED",
            "The leave draft preview no longer matches the selected candidate.",
        )


def confirm_leave_draft(
    db: Session,
    actor: Employee,
    preview: LeaveDraftExactPreview,
    confirmation_token: str,
) -> Approval:
    confirmation = decode_leave_draft_confirmation_token(confirmation_token)
    if confirmation.employee_id != actor.id:
        raise AuthorizationError("This leave draft confirmation belongs to another employee")
    if not hmac.compare_digest(confirmation.preview_hash, _canonical_hash(preview)):
        raise ConflictError(
            "LEAVE_PREVIEW_CHANGED",
            "The leave draft preview changed after it was prepared.",
        )
    if not hmac.compare_digest(
        confirmation.candidate_hash,
        _canonical_hash(preview.candidate),
    ):
        raise ConflictError(
            "LEAVE_PREVIEW_CHANGED",
            "The selected leave candidate changed after it was prepared.",
        )

    existing = db.scalar(
        select(Approval).where(
            Approval.source_confirmation_id == confirmation.confirmation_id,
            Approval.author_id == actor.id,
        )
    )
    if existing is not None:
        return approval_service.get_approval(db, actor, existing.id)

    _validate_approval_matches_preview(db, actor, preview)
    account = _leave_account(db, actor, preview.candidate.start_date.year, lock=True)
    if (
        account.version != confirmation.account_version
        or account.version != preview.account_version
        or account.available_days != preview.available_days
        or account.available_days < preview.requested_days
    ):
        raise ConflictError(
            "LEAVE_DRAFT_STALE",
            "The leave account changed after preview. Search again.",
        )
    manager = _manager(db, actor)
    if manager.id != confirmation.manager_id or manager.id != preview.manager.id:
        raise ConflictError(
            "LEAVE_DRAFT_STALE",
            "The approver changed after preview. Prepare the draft again.",
        )
    policy_fingerprint = policy_retrieval.active_policy_fingerprint(db, PolicyType.LEAVE)
    if (
        not hmac.compare_digest(policy_fingerprint, confirmation.policy_fingerprint)
        or not hmac.compare_digest(policy_fingerprint, preview.policy_fingerprint)
    ):
        raise ConflictError(
            "LEAVE_DRAFT_STALE",
            "The active leave policy changed after preview. Prepare the draft again.",
        )
    calendar_fingerprint = leave_calendar_fingerprint(
        db,
        actor,
        preview.candidate.start_date,
        preview.candidate.end_date,
    )
    if (
        not hmac.compare_digest(calendar_fingerprint, confirmation.calendar_fingerprint)
        or not hmac.compare_digest(calendar_fingerprint, preview.calendar_fingerprint)
    ):
        raise ConflictError(
            "LEAVE_DRAFT_STALE",
            "The work calendar changed after preview. Search again.",
        )
    _validated_candidate(db, actor, preview.candidate)
    return approval_service.create_draft(
        db,
        actor,
        preview.approval,
        source_confirmation_id=confirmation.confirmation_id,
    )

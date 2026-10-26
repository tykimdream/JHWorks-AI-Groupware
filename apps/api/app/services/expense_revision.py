"""Read-only AI proposal; version-bound explicit application; deterministic decision evidence."""

import hashlib
import hmac
import json

from sqlalchemy.orm import Session

from app.ai.approval_draft import ApprovalDraftProvider
from app.ai.policy_embedding import PolicyEmbeddingProvider
from app.core.config import get_settings
from app.core.errors import AuthorizationError, ConflictError, DomainValidationError
from app.core.security import create_expense_revision_token, decode_expense_revision_token
from app.models.approval import Approval
from app.models.employee import Employee
from app.models.enums import ApprovalLineStatus, ApprovalStatus, ApprovalType
from app.schemas.approval import ApprovalCreate
from app.schemas.approval_draft_ai import ApprovalDraftPrepareRequest
from app.schemas.expense_revision import (
    ExpenseChange,
    ExpenseDecisionBrief,
    ExpenseRevisionApply,
    ExpenseRevisionRequest,
    ExpenseRevisionResponse,
)
from app.services import approval as approvals
from app.services.approval_draft import (
    _not_applicable_policy_context,
    prepare_approval_draft,
    preview_hash,
)
from app.services.expense_checks import check_expense
from app.services.expense_policy import expense_policy_fingerprint, validate_expense_policy


def rejection_comment(approval: Approval) -> str | None:
    lines = sorted(
        (line for line in approval.lines if line.status == ApprovalLineStatus.REJECTED),
        key=lambda line: (line.round, line.step),
        reverse=True,
    )
    return lines[0].comment if lines else None


def _require_rejected(approval: Approval, actor: Employee, version: int) -> None:
    if approval.author_id != actor.id:
        raise AuthorizationError("Only the author can prepare corrections")
    if approval.version != version:
        raise ConflictError("VERSION_CONFLICT", "Refresh the document and prepare again")
    if approval.type != ApprovalType.EXPENSE or approval.status != ApprovalStatus.REJECTED:
        raise ConflictError("INVALID_STATUS", "A rejected expense is required")


def _fields(approval: Approval) -> ApprovalCreate:
    return ApprovalCreate(
        type=approval.type,
        title=approval.title,
        content=approval.content,
        amount=approval.amount,
        details=approval.details,
        attachment_metadata=approval.attachment_metadata,
    )


def _snapshot(approval_id: str, version: int, preview: ApprovalCreate, policy: str) -> str:
    return hashlib.sha256(
        json.dumps(
            [approval_id, version, preview_hash(preview), policy],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _values(preview: ApprovalCreate) -> dict[str, str | int | None]:
    result: dict[str, str | int | None] = {
        "title": preview.title,
        "content": preview.content,
        "amount": preview.amount,
    }
    for key, value in preview.details.model_dump(mode="json", by_alias=True).items():
        if key != "kind" and (value is None or isinstance(value, (str, int))):
            result[f"details.{key}"] = value
    return result


def prepare_revision(
    db: Session,
    actor: Employee,
    approval_id: str,
    payload: ExpenseRevisionRequest,
    provider: ApprovalDraftProvider,
    embedding_provider: PolicyEmbeddingProvider,
) -> ExpenseRevisionResponse:
    approval = approvals.get_approval(db, actor, approval_id)
    _require_rejected(approval, actor, payload.version)
    # This is a new private workflow, not an expansion of the public draft capability.
    if get_settings().public_demo_enabled:
        raise AuthorizationError("AI corrections are not enabled in the public demo")
    reason = rejection_comment(approval)
    if not reason:
        raise DomainValidationError("REJECTION_REQUIRED", "A rejection comment is required")
    before = _fields(approval)
    labels = {
        "expenseDate": "지출일",
        "merchant": "사용처",
        "category": "분류",
        "purpose": "목적",
        "receiptReference": "증빙 참조",
    }
    parts = (
        ["경비 정산", f"금액: {before.amount}원"] if before.amount is not None else ["경비 정산"]
    )
    for key, label in labels.items():
        value = approval.details.get(key)
        if isinstance(value, str) and any(char in value for char in ";；\n\r"):
            raise DomainValidationError(
                "REVISION_FACT_FORMAT", "Use direct editing for multiline or delimited facts"
            )
        if value:
            parts.append(f"{label}: {value}")
    prepared = prepare_approval_draft(
        db,
        actor,
        ApprovalDraftPrepareRequest(request="; ".join(parts), answers=payload.answers),
        provider,
        embedding_provider,
        revision_context=reason,
        issue_confirmation=False,
    )
    # Never sign a different intent, and never turn the correction into a new-document token.
    if prepared.preview and prepared.preview.type != ApprovalType.EXPENSE:
        raise DomainValidationError("NOT_AN_EXPENSE", "Correction must remain an expense")
    db.expire_all()
    latest = approvals.get_approval(db, actor, approval_id)
    _require_rejected(latest, actor, payload.version)
    changes: list[ExpenseChange] = []
    token = None
    if prepared.preview:
        prepared.preview.attachment_metadata = before.attachment_metadata
        original, proposed = _values(before), _values(prepared.preview)
        changes = [
            ExpenseChange(field=key, before=original[key], after=value)
            for key, value in proposed.items()
            if original.get(key) != value
        ]
        fingerprint = prepared.policy_validation.fingerprint if prepared.policy_validation else ""
        if fingerprint != expense_policy_fingerprint(db):
            raise ConflictError("POLICY_CHANGED", "Prepare again after policy changes")
        token = create_expense_revision_token(
            actor.id,
            _snapshot(approval_id, payload.version, prepared.preview, fingerprint),
        )
    return ExpenseRevisionResponse(
        approval_id=approval_id,
        version=payload.version,
        rejection_comment=reason,
        prepared=prepared,
        changes=changes,
        apply_token=token,
    )


def apply_revision(
    db: Session,
    actor: Employee,
    approval_id: str,
    payload: ExpenseRevisionApply,
) -> Approval:
    if get_settings().public_demo_enabled:
        raise AuthorizationError("AI corrections are not enabled in the public demo")
    approval = approvals.get_approval(db, actor, approval_id)
    _require_rejected(approval, actor, payload.version)
    employee_id, signed = decode_expense_revision_token(payload.apply_token)
    if employee_id != actor.id:
        raise AuthorizationError("This proposal belongs to another author")
    actual = _snapshot(
        approval_id, payload.version, payload.preview, expense_policy_fingerprint(db)
    )
    if not hmac.compare_digest(actual, signed):
        raise ConflictError("REVISION_CHANGED", "The proposal or policies changed. Prepare again")
    return approvals.apply_rejected_expense(
        db, actor, approval_id, payload.version, payload.preview
    )


def decision_brief(
    db: Session,
    actor: Employee,
    approval_id: str,
    version: int,
) -> ExpenseDecisionBrief:
    approval = approvals.get_approval(db, actor, approval_id)
    pending = [line for line in approval.lines if line.status == ApprovalLineStatus.PENDING]
    if (
        approval.status != ApprovalStatus.PENDING
        or len(pending) != 1
        or pending[0].approver_id != actor.id
    ):
        raise AuthorizationError("Only the current approver can request a decision brief")
    if approval.version != version:
        raise ConflictError("VERSION_CONFLICT", "Refresh the document before reviewing")
    if approval.type != ApprovalType.EXPENSE:
        raise DomainValidationError("NOT_AN_EXPENSE", "An expense is required")
    reference = approval.details.get("receiptReference")
    return ExpenseDecisionBrief(
        approval_id=approval_id,
        version=approval.version,
        checks=check_expense(db, actor, approval_id),
        policy=validate_expense_policy(db, _fields(approval), _not_applicable_policy_context()),
        rejection_comment=rejection_comment(approval),
        receipt_reference=reference if isinstance(reference, str) else None,
    )

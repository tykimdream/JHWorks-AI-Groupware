from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.leave_assistant import LeaveAssistantProvider
from app.ai.policy_embedding import PolicyEmbeddingProvider
from app.core.errors import (
    AppError,
    AuthorizationError,
    ConflictError,
    ServiceUnavailableError,
)
from app.models.approval import Approval
from app.models.employee import Employee
from app.models.enums import ApprovalStatus, LeaveAgentStatus
from app.models.leave_agent import LeaveAgentRun
from app.schemas.leave_agent import (
    LeaveAgentConsultationRead,
    LeaveAgentDraftConfirmRead,
    LeaveAgentDraftPrepareRead,
    LeaveAgentRunRead,
    LeaveAgentStartRequest,
    LeaveAgentTraceRead,
    LeaveSubmitDecision,
    LeaveSubmitPrepareRead,
    LeaveSubmitPreview,
    LeaveSubmitResumeRead,
)
from app.schemas.leave_assistant import (
    LeaveAssistantRequest,
    LeaveAssistantStatus,
)
from app.schemas.leave_draft_tool import (
    LeaveDraftConfirmRequest,
    LeaveDraftPrepareRequest,
)
from app.services import approval as approval_service
from app.services import leave_assistant, leave_draft_tool, leave_submit_tool
from app.services.mappers import approval_read

TERMINAL_STATUSES = {
    LeaveAgentStatus.SUBMITTED,
    LeaveAgentStatus.CANCELED,
    LeaveAgentStatus.EXPIRED,
    LeaveAgentStatus.STALE,
}


def _trace(
    run: LeaveAgentRun,
    to_status: LeaveAgentStatus,
    event: str,
    result_code: str,
) -> None:
    now = datetime.now(UTC)
    previous = run.status
    trace = list(run.trace)
    trace.append(
        {
            "at": now.isoformat(),
            "fromStatus": previous.value if previous else None,
            "toStatus": to_status.value,
            "event": event,
            "resultCode": result_code,
        }
    )
    run.trace = trace[-100:]
    run.status = to_status
    run.version += 1
    run.updated_at = now
    run.completed_at = now if to_status in TERMINAL_STATUSES else None


def run_read(run: LeaveAgentRun) -> LeaveAgentRunRead:
    return LeaveAgentRunRead(
        id=run.id,
        status=run.status,
        approval_id=run.approval_id,
        retry_count=run.retry_count,
        last_error_code=run.last_error_code,
        version=run.version,
        trace=[LeaveAgentTraceRead.model_validate(item) for item in run.trace],
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


def _get_run(
    db: Session,
    actor: Employee,
    run_id: str,
    *,
    lock: bool = False,
) -> LeaveAgentRun:
    statement = select(LeaveAgentRun).where(LeaveAgentRun.id == run_id)
    if lock:
        statement = statement.with_for_update()
    run = db.scalar(statement)
    if run is None:
        raise ConflictError("LEAVE_AGENT_RUN_NOT_FOUND", "The leave workflow was not found.")
    if run.actor_id != actor.id:
        raise AuthorizationError("This leave workflow belongs to another employee")
    return run


def get_run(db: Session, actor: Employee, run_id: str) -> LeaveAgentRunRead:
    return run_read(_get_run(db, actor, run_id))


def _consult(
    db: Session,
    actor: Employee,
    run: LeaveAgentRun,
    provider: LeaveAssistantProvider,
    embedding_provider: PolicyEmbeddingProvider,
) -> LeaveAgentConsultationRead:
    try:
        result = leave_assistant.consult_leave_availability(
            db,
            actor,
            LeaveAssistantRequest(request=run.request, answers=run.answers),
            provider,
            embedding_provider,
        )
    except ServiceUnavailableError as exc:
        run = _get_run(db, actor, run.id, lock=True)
        run.last_error_code = exc.code
        _trace(
            run,
            LeaveAgentStatus.CONSULTATION_FAILED,
            "structure_leave_request",
            exc.code,
        )
        db.commit()
        return LeaveAgentConsultationRead(run=run_read(run), consultation=None)

    run = _get_run(db, actor, run.id, lock=True)
    run.consultation_result = result.model_dump(mode="json", by_alias=True)
    run.last_error_code = None
    if result.status == LeaveAssistantStatus.NEEDS_INPUT:
        next_status = LeaveAgentStatus.NEEDS_INPUT
    elif result.status == LeaveAssistantStatus.READY:
        next_status = LeaveAgentStatus.CANDIDATES_READY
    else:
        next_status = LeaveAgentStatus.CANCELED
    _trace(run, next_status, "structure_leave_request", result.status.value)
    db.commit()
    return LeaveAgentConsultationRead(run=run_read(run), consultation=result)


def start_run(
    db: Session,
    actor: Employee,
    payload: LeaveAgentStartRequest,
    provider: LeaveAssistantProvider,
    embedding_provider: PolicyEmbeddingProvider,
) -> LeaveAgentConsultationRead:
    run = LeaveAgentRun(
        id=f"leave_run_{uuid4().hex}",
        actor_id=actor.id,
        status=LeaveAgentStatus.CONSULTING,
        request=payload.request.strip(),
        answers=[answer.strip() for answer in payload.answers if answer.strip()],
        trace=[],
    )
    db.add(run)
    db.flush()
    _trace(run, LeaveAgentStatus.CONSULTING, "start", "STARTED")
    db.commit()
    return _consult(db, actor, run, provider, embedding_provider)


def answer_consultation(
    db: Session,
    actor: Employee,
    run_id: str,
    answer: str,
    provider: LeaveAssistantProvider,
    embedding_provider: PolicyEmbeddingProvider,
) -> LeaveAgentConsultationRead:
    run = _get_run(db, actor, run_id, lock=True)
    if run.status != LeaveAgentStatus.NEEDS_INPUT:
        raise ConflictError(
            "INVALID_LEAVE_AGENT_STATE",
            "This workflow is not waiting for a consultation answer.",
        )
    run.answers = [*run.answers, answer.strip()]
    _trace(run, LeaveAgentStatus.CONSULTING, "answer", "ANSWER_RECORDED")
    db.commit()
    return _consult(db, actor, run, provider, embedding_provider)


def retry_consultation(
    db: Session,
    actor: Employee,
    run_id: str,
    provider: LeaveAssistantProvider,
    embedding_provider: PolicyEmbeddingProvider,
) -> LeaveAgentConsultationRead:
    run = _get_run(db, actor, run_id, lock=True)
    if run.status != LeaveAgentStatus.CONSULTATION_FAILED:
        raise ConflictError(
            "INVALID_LEAVE_AGENT_STATE",
            "Only a failed consultation can be retried.",
        )
    run.retry_count += 1
    _trace(run, LeaveAgentStatus.CONSULTING, "retry_consultation", "RETRYING")
    db.commit()
    return _consult(db, actor, run, provider, embedding_provider)


def prepare_draft(
    db: Session,
    actor: Employee,
    run_id: str,
    payload: LeaveDraftPrepareRequest,
    embedding_provider: PolicyEmbeddingProvider,
) -> LeaveAgentDraftPrepareRead:
    run = _get_run(db, actor, run_id, lock=True)
    if run.status not in {
        LeaveAgentStatus.CANDIDATES_READY,
        LeaveAgentStatus.AWAITING_DRAFT_CONFIRMATION,
    }:
        raise ConflictError(
            "INVALID_LEAVE_AGENT_STATE",
            "The workflow is not ready for a Draft preview.",
        )
    preparation = leave_draft_tool.prepare_leave_draft(
        db,
        actor,
        payload,
        embedding_provider,
    )
    run.draft_preview = preparation.preview.model_dump(mode="json", by_alias=True)
    run.last_error_code = None
    _trace(
        run,
        LeaveAgentStatus.AWAITING_DRAFT_CONFIRMATION,
        "prepare_leave_draft",
        "INTERRUPTED",
    )
    db.commit()
    return LeaveAgentDraftPrepareRead(run=run_read(run), preparation=preparation)


def confirm_draft(
    db: Session,
    actor: Employee,
    run_id: str,
    payload: LeaveDraftConfirmRequest,
) -> LeaveAgentDraftConfirmRead:
    run = _get_run(db, actor, run_id, lock=True)
    if run.status == LeaveAgentStatus.DRAFT_CREATED and run.approval_id is not None:
        approval = approval_service.get_approval(db, actor, run.approval_id)
        return LeaveAgentDraftConfirmRead(run=run_read(run), approval=approval_read(approval))
    if run.status != LeaveAgentStatus.AWAITING_DRAFT_CONFIRMATION:
        raise ConflictError(
            "INVALID_LEAVE_AGENT_STATE",
            "The workflow is not waiting for Draft confirmation.",
        )
    stored_preview = run.draft_preview
    if stored_preview != payload.preview.model_dump(mode="json", by_alias=True):
        raise ConflictError(
            "LEAVE_PREVIEW_CHANGED",
            "The durable workflow preview does not match the confirmation.",
        )
    approval = leave_draft_tool.confirm_leave_draft(
        db,
        actor,
        payload.preview,
        payload.confirmation_token,
    )
    run = _get_run(db, actor, run_id, lock=True)
    run.approval_id = approval.id
    run.last_error_code = None
    _trace(run, LeaveAgentStatus.DRAFT_CREATED, "create_leave_draft", "DRAFT_CREATED")
    db.commit()
    return LeaveAgentDraftConfirmRead(run=run_read(run), approval=approval_read(approval))


def prepare_submit(
    db: Session,
    actor: Employee,
    run_id: str,
    expected_approval_version: int,
) -> LeaveSubmitPrepareRead:
    run = _get_run(db, actor, run_id, lock=True)
    if run.approval_id is None or run.status not in {
        LeaveAgentStatus.DRAFT_CREATED,
        LeaveAgentStatus.AWAITING_SUBMIT_CONFIRMATION,
    }:
        raise ConflictError(
            "INVALID_LEAVE_AGENT_STATE",
            "The workflow has no Draft ready for submission.",
        )
    preview = leave_submit_tool.build_submit_preview(
        db,
        actor,
        run.approval_id,
        expected_approval_version,
    )
    token, confirmation_id, expires_at = leave_submit_tool.create_submit_confirmation(
        actor,
        run.id,
        preview,
    )
    run.submit_preview = preview.model_dump(mode="json", by_alias=True)
    run.submit_confirmation_id = confirmation_id
    run.submit_confirmation_expires_at = expires_at
    run.last_error_code = None
    _trace(
        run,
        LeaveAgentStatus.AWAITING_SUBMIT_CONFIRMATION,
        "prepare_leave_submit",
        "INTERRUPTED",
    )
    db.commit()
    return LeaveSubmitPrepareRead(
        run=run_read(run),
        preview=preview,
        confirmation_token=token,
        expires_at=expires_at,
    )


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _stored_submit_preview(run: LeaveAgentRun) -> LeaveSubmitPreview:
    if run.submit_preview is None:
        raise ConflictError(
            "INVALID_LEAVE_AGENT_STATE",
            "The workflow has no stored submission preview.",
        )
    return LeaveSubmitPreview.model_validate(run.submit_preview)


def _approval_for_run(db: Session, actor: Employee, run: LeaveAgentRun) -> Approval:
    if run.approval_id is None:
        raise ConflictError("INVALID_LEAVE_AGENT_STATE", "The workflow has no approval.")
    return approval_service.get_approval(db, actor, run.approval_id)


def _mark_failure(
    db: Session,
    actor: Employee,
    run_id: str,
    status: LeaveAgentStatus,
    code: str,
) -> None:
    db.rollback()
    run = _get_run(db, actor, run_id, lock=True)
    run.last_error_code = code
    if status == LeaveAgentStatus.FAILED:
        run.retry_count += 1
    _trace(run, status, "submit_leave", code)
    db.commit()


def _reconcile_committed_submit(
    db: Session,
    actor: Employee,
    run_id: str,
) -> LeaveSubmitResumeRead | None:
    db.rollback()
    run = _get_run(db, actor, run_id, lock=True)
    approval = _approval_for_run(db, actor, run)
    if approval.status != ApprovalStatus.PENDING:
        return None
    run.last_error_code = None
    _trace(run, LeaveAgentStatus.SUBMITTED, "reconcile_submit", "ALREADY_SUBMITTED")
    db.commit()
    return LeaveSubmitResumeRead(run=run_read(run), approval=approval_read(approval))


def resume_submit(
    db: Session,
    actor: Employee,
    run_id: str,
    decision: LeaveSubmitDecision,
    preview: LeaveSubmitPreview,
    confirmation_token: str,
) -> LeaveSubmitResumeRead:
    run = _get_run(db, actor, run_id, lock=True)
    stored_preview = _stored_submit_preview(run)
    if stored_preview != preview:
        raise ConflictError(
            "LEAVE_SUBMIT_PREVIEW_CHANGED",
            "The durable submission preview does not match the confirmation.",
        )

    if run.status == LeaveAgentStatus.SUBMITTED:
        leave_submit_tool.validate_submit_token_identity(
            actor,
            run.id,
            preview,
            confirmation_token,
        )
        approval = _approval_for_run(db, actor, run)
        return LeaveSubmitResumeRead(run=run_read(run), approval=approval_read(approval))
    if run.status == LeaveAgentStatus.CANCELED:
        leave_submit_tool.validate_submit_token_identity(
            actor,
            run.id,
            preview,
            confirmation_token,
        )
        approval = _approval_for_run(db, actor, run)
        return LeaveSubmitResumeRead(run=run_read(run), approval=approval_read(approval))
    if run.status not in {
        LeaveAgentStatus.AWAITING_SUBMIT_CONFIRMATION,
        LeaveAgentStatus.SUBMITTING,
        LeaveAgentStatus.FAILED,
    }:
        raise ConflictError(
            "INVALID_LEAVE_AGENT_STATE",
            "The workflow is not waiting for submission confirmation.",
        )
    if (
        run.submit_confirmation_expires_at is None
        or _utc(run.submit_confirmation_expires_at) <= datetime.now(UTC)
    ):
        _trace(run, LeaveAgentStatus.EXPIRED, "resume_submit", "CONFIRMATION_EXPIRED")
        db.commit()
        raise ConflictError(
            "INVALID_LEAVE_SUBMIT_CONFIRMATION",
            "The leave submission confirmation expired without changing the Draft.",
        )
    leave_submit_tool.validate_submit_token_identity(
        actor,
        run.id,
        preview,
        confirmation_token,
    )
    approval = _approval_for_run(db, actor, run)
    if decision == LeaveSubmitDecision.CANCEL:
        _trace(run, LeaveAgentStatus.CANCELED, "resume_submit", "USER_CANCELED")
        db.commit()
        return LeaveSubmitResumeRead(run=run_read(run), approval=approval_read(approval))

    if approval.status == ApprovalStatus.PENDING:
        _trace(run, LeaveAgentStatus.SUBMITTED, "reconcile_submit", "ALREADY_SUBMITTED")
        run.last_error_code = None
        db.commit()
        return LeaveSubmitResumeRead(run=run_read(run), approval=approval_read(approval))

    try:
        approval, snapshot, _ = leave_submit_tool.validate_submit_confirmation(
            db,
            actor,
            run.id,
            preview,
            confirmation_token,
        )
    except AppError as exc:
        _mark_failure(db, actor, run.id, LeaveAgentStatus.STALE, exc.code)
        raise ConflictError(
            "LEAVE_SUBMIT_STALE",
            "Submission inputs changed. The Draft was not submitted.",
        ) from exc

    run = _get_run(db, actor, run.id, lock=True)
    _trace(run, LeaveAgentStatus.SUBMITTING, "resume_submit", "CONFIRMED")
    db.commit()
    try:
        approval = leave_submit_tool.execute_confirmed_submit(db, actor, approval, snapshot)
    except AppError as exc:
        reconciled = _reconcile_committed_submit(db, actor, run.id)
        if reconciled is not None:
            return reconciled
        target = (
            LeaveAgentStatus.STALE
            if exc.code
            in {
                "VERSION_CONFLICT",
                "INVALID_STATUS",
                "LEAVE_SUBMIT_STALE",
                "INSUFFICIENT_LEAVE_BALANCE",
                "MANAGER_UNAVAILABLE",
            }
            else LeaveAgentStatus.FAILED
        )
        _mark_failure(db, actor, run.id, target, exc.code)
        raise
    except Exception as exc:
        reconciled = _reconcile_committed_submit(db, actor, run.id)
        if reconciled is not None:
            return reconciled
        _mark_failure(
            db,
            actor,
            run.id,
            LeaveAgentStatus.FAILED,
            "LEAVE_SUBMIT_RETRYABLE",
        )
        raise ServiceUnavailableError(
            "LEAVE_SUBMIT_RETRYABLE",
            "The submit Tool failed. Resume the same workflow to retry safely.",
        ) from exc

    run = _get_run(db, actor, run.id, lock=True)
    run.approval_id = approval.id
    run.last_error_code = None
    _trace(run, LeaveAgentStatus.SUBMITTED, "submit_leave", "SUBMITTED")
    db.commit()
    return LeaveSubmitResumeRead(run=run_read(run), approval=approval_read(approval))

from fastapi import APIRouter

from app.api.dependencies import (
    CurrentEmployee,
    DbSession,
    LeaveAssistantProviderDependency,
    PolicyEmbeddingProviderDependency,
)
from app.schemas.leave_agent import (
    LeaveAgentAnswerRequest,
    LeaveAgentConsultationRead,
    LeaveAgentDraftConfirmRead,
    LeaveAgentDraftPrepareRead,
    LeaveAgentRunRead,
    LeaveAgentStartRequest,
    LeaveSubmitPrepareRead,
    LeaveSubmitPrepareRequest,
    LeaveSubmitResumeRead,
    LeaveSubmitResumeRequest,
)
from app.schemas.leave_draft_tool import LeaveDraftConfirmRequest, LeaveDraftPrepareRequest
from app.services import leave_agent as leave_agent_service

router = APIRouter(prefix="/leave-agent/runs", tags=["leave-agent"])


@router.post("", response_model=LeaveAgentConsultationRead, status_code=201)
def start_leave_agent(
    payload: LeaveAgentStartRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: LeaveAssistantProviderDependency,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> LeaveAgentConsultationRead:
    return leave_agent_service.start_run(
        db,
        current_employee,
        payload,
        provider,
        embedding_provider,
    )


@router.get("/{run_id}", response_model=LeaveAgentRunRead)
def get_leave_agent_run(
    run_id: str,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> LeaveAgentRunRead:
    return leave_agent_service.get_run(db, current_employee, run_id)


@router.post("/{run_id}/consultation/answer", response_model=LeaveAgentConsultationRead)
def answer_leave_agent(
    run_id: str,
    payload: LeaveAgentAnswerRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: LeaveAssistantProviderDependency,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> LeaveAgentConsultationRead:
    return leave_agent_service.answer_consultation(
        db,
        current_employee,
        run_id,
        payload.answer,
        provider,
        embedding_provider,
    )


@router.post("/{run_id}/consultation/retry", response_model=LeaveAgentConsultationRead)
def retry_leave_agent(
    run_id: str,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: LeaveAssistantProviderDependency,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> LeaveAgentConsultationRead:
    return leave_agent_service.retry_consultation(
        db,
        current_employee,
        run_id,
        provider,
        embedding_provider,
    )


@router.post("/{run_id}/draft/prepare", response_model=LeaveAgentDraftPrepareRead)
def prepare_leave_agent_draft(
    run_id: str,
    payload: LeaveDraftPrepareRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> LeaveAgentDraftPrepareRead:
    return leave_agent_service.prepare_draft(
        db,
        current_employee,
        run_id,
        payload,
        embedding_provider,
    )


@router.post("/{run_id}/draft/confirm", response_model=LeaveAgentDraftConfirmRead)
def confirm_leave_agent_draft(
    run_id: str,
    payload: LeaveDraftConfirmRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> LeaveAgentDraftConfirmRead:
    return leave_agent_service.confirm_draft(db, current_employee, run_id, payload)


@router.post("/{run_id}/submit/prepare", response_model=LeaveSubmitPrepareRead)
def prepare_leave_agent_submit(
    run_id: str,
    payload: LeaveSubmitPrepareRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> LeaveSubmitPrepareRead:
    return leave_agent_service.prepare_submit(
        db,
        current_employee,
        run_id,
        payload.approval_version,
    )


@router.post("/{run_id}/submit/resume", response_model=LeaveSubmitResumeRead)
def resume_leave_agent_submit(
    run_id: str,
    payload: LeaveSubmitResumeRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> LeaveSubmitResumeRead:
    return leave_agent_service.resume_submit(
        db,
        current_employee,
        run_id,
        payload.decision,
        payload.preview,
        payload.confirmation_token,
    )

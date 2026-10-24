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

router = APIRouter(prefix="/leave-agent/runs", tags=["근태·휴가"])


@router.post(
    "", response_model=LeaveAgentConsultationRead, status_code=201, summary="휴가 신청 상담 시작"
)
def start_leave_agent(
    payload: LeaveAgentStartRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: LeaveAssistantProviderDependency,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> LeaveAgentConsultationRead:
    """
    상담부터 초안 저장·제출까지 이어갈 수 있는 휴가 신청 작업을
    시작합니다. 초안 저장과 제출은 각각 사용자 확인이 필요합니다.
    """
    return leave_agent_service.start_run(
        db,
        current_employee,
        payload,
        provider,
        embedding_provider,
    )


@router.get("/{run_id}", response_model=LeaveAgentRunRead, summary="휴가 신청 진행 상태 조회")
def get_leave_agent_run(
    run_id: str,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> LeaveAgentRunRead:
    """내가 시작한 휴가 신청 작업의 현재 단계와 처리 결과를 조회합니다."""
    return leave_agent_service.get_run(db, current_employee, run_id)


@router.post(
    "/{run_id}/consultation/answer",
    response_model=LeaveAgentConsultationRead,
    summary="휴가 상담 추가 질문에 답변",
)
def answer_leave_agent(
    run_id: str,
    payload: LeaveAgentAnswerRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: LeaveAssistantProviderDependency,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> LeaveAgentConsultationRead:
    """
    진행 중인 상담의 부족한 정보를 보완하고 다음 질문 또는 휴가 후보를
    받습니다.
    """
    return leave_agent_service.answer_consultation(
        db,
        current_employee,
        run_id,
        payload.answer,
        provider,
        embedding_provider,
    )


@router.post(
    "/{run_id}/consultation/retry",
    response_model=LeaveAgentConsultationRead,
    summary="휴가 상담 재시도",
)
def retry_leave_agent(
    run_id: str,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: LeaveAssistantProviderDependency,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> LeaveAgentConsultationRead:
    """
    실패한 상담 단계를 다시 실행합니다. 저장·제출을 자동으로 실행하지
    않습니다.
    """
    return leave_agent_service.retry_consultation(
        db,
        current_employee,
        run_id,
        provider,
        embedding_provider,
    )


@router.post(
    "/{run_id}/draft/prepare",
    response_model=LeaveAgentDraftPrepareRead,
    summary="휴가 초안 저장 전 확인 내용 조회",
)
def prepare_leave_agent_draft(
    run_id: str,
    payload: LeaveDraftPrepareRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> LeaveAgentDraftPrepareRead:
    """
    선택한 후보의 날짜·차감 일수·결재자를 확인하고 초안 저장용
    미리보기를 받습니다.
    """
    return leave_agent_service.prepare_draft(
        db,
        current_employee,
        run_id,
        payload,
        embedding_provider,
    )


@router.post(
    "/{run_id}/draft/confirm",
    response_model=LeaveAgentDraftConfirmRead,
    summary="휴가 신청 작업의 초안 저장 확인",
)
def confirm_leave_agent_draft(
    run_id: str,
    payload: LeaveDraftConfirmRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> LeaveAgentDraftConfirmRead:
    """
    확인한 미리보기로 휴가 초안을 한 번만 저장합니다. 연차와 일정이
    바뀌었다면 다시 확인해야 합니다.
    """
    return leave_agent_service.confirm_draft(db, current_employee, run_id, payload)


@router.post(
    "/{run_id}/submit/prepare",
    response_model=LeaveSubmitPrepareRead,
    summary="휴가 제출 전 확인 내용 조회",
)
def prepare_leave_agent_submit(
    run_id: str,
    payload: LeaveSubmitPrepareRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> LeaveSubmitPrepareRead:
    """
    저장된 초안의 날짜·차감 연차·결재자·문서 버전을 다시 확인하고
    제출용 미리보기를 받습니다.
    """
    return leave_agent_service.prepare_submit(
        db,
        current_employee,
        run_id,
        payload.approval_version,
    )


@router.post(
    "/{run_id}/submit/resume",
    response_model=LeaveSubmitResumeRead,
    summary="휴가 제출 확인·이어하기",
)
def resume_leave_agent_submit(
    run_id: str,
    payload: LeaveSubmitResumeRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> LeaveSubmitResumeRead:
    """
    제출 미리보기에 동의한 뒤 휴가 결재를 제출합니다. 재시도해도
    결재선과 연차 예약은 중복 생성하지 않습니다.
    """
    return leave_agent_service.resume_submit(
        db,
        current_employee,
        run_id,
        payload.decision,
        payload.preview,
        payload.confirmation_token,
    )

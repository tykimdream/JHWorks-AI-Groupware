from fastapi import APIRouter

from app.api.dependencies import (
    CurrentEmployee,
    DbSession,
    LeaveAssistantProviderDependency,
    PolicyEmbeddingProviderDependency,
)
from app.schemas.leave_assistant import LeaveAssistantRequest, LeaveAssistantResponse
from app.services import leave_assistant as leave_assistant_service

router = APIRouter(prefix="/leave-assistant", tags=["근태·휴가"])


@router.post("/consult", response_model=LeaveAssistantResponse, summary="AI 휴가 일정 상담")
def consult_leave_availability(
    payload: LeaveAssistantRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: LeaveAssistantProviderDependency,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> LeaveAssistantResponse:
    """
    자연어로 희망 기간과 일수를 입력해 휴가 후보를 상담합니다. 연차와
    일정은 서버가 계산하며 상담만으로 신청서를 저장하지 않습니다.
    """
    return leave_assistant_service.consult_leave_availability(
        db,
        current_employee,
        payload,
        provider,
        embedding_provider,
    )

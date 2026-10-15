from fastapi import APIRouter

from app.api.dependencies import (
    CurrentEmployee,
    DbSession,
    LeaveAssistantProviderDependency,
    PolicyEmbeddingProviderDependency,
)
from app.schemas.leave_assistant import LeaveAssistantRequest, LeaveAssistantResponse
from app.services import leave_assistant as leave_assistant_service

router = APIRouter(prefix="/leave-assistant", tags=["leave-assistant"])


@router.post("/consult", response_model=LeaveAssistantResponse)
def consult_leave_availability(
    payload: LeaveAssistantRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: LeaveAssistantProviderDependency,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> LeaveAssistantResponse:
    return leave_assistant_service.consult_leave_availability(
        db,
        current_employee,
        payload,
        provider,
        embedding_provider,
    )

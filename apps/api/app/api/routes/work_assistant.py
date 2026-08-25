from fastapi import APIRouter

from app.api.dependencies import (
    CurrentEmployee,
    DbSession,
    PolicyEmbeddingProviderDependency,
    WorkAssistantProviderDependency,
)
from app.schemas.work_assistant import WorkAssistantRequest, WorkAssistantResponse
from app.services import work_assistant as work_assistant_service

router = APIRouter(prefix="/work-assistant", tags=["work-assistant"])


@router.post("/query", response_model=WorkAssistantResponse)
def query_work_assistant(
    payload: WorkAssistantRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: WorkAssistantProviderDependency,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> WorkAssistantResponse:
    return work_assistant_service.answer_work_question(
        db,
        current_employee,
        payload,
        provider,
        embedding_provider,
    )

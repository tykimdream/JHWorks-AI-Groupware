from fastapi import APIRouter

from app.api.dependencies import (
    CurrentEmployee,
    DbSession,
    PolicyEmbeddingProviderDependency,
    WorkAssistantProviderDependency,
)
from app.schemas.work_assistant import WorkAssistantRequest, WorkAssistantResponse
from app.services import work_assistant as work_assistant_service

router = APIRouter(prefix="/work-assistant", tags=["업무 도우미"])


@router.post("/query", response_model=WorkAssistantResponse, summary="AI로 내 업무 조회")
def query_work_assistant(
    payload: WorkAssistantRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: WorkAssistantProviderDependency,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> WorkAssistantResponse:
    """
    현재 사용자의 조직·결재·정책 정보를 제한된 조회 도구로 확인하고
    답변과 실행 기록을 반환합니다. 업무 데이터를 변경하지 않습니다.
    """
    return work_assistant_service.answer_work_question(
        db,
        current_employee,
        payload,
        provider,
        embedding_provider,
    )

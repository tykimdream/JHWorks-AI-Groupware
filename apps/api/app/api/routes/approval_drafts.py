from fastapi import APIRouter

from app.api.dependencies import (
    AIApprovalDraftProvider,
    CurrentEmployee,
    DbSession,
    PolicyEmbeddingProviderDependency,
)
from app.schemas.approval import ApprovalRead
from app.schemas.approval_draft_ai import (
    ApprovalDraftConfirmRequest,
    ApprovalDraftPrepareRequest,
    ApprovalDraftPrepareResponse,
)
from app.services import approval_draft as approval_draft_service
from app.services.mappers import approval_read

router = APIRouter(prefix="/approval-draft-assistant", tags=["전자결재"])


@router.post("/prepare", response_model=ApprovalDraftPrepareResponse, summary="AI 결재 초안 준비")
def prepare_approval_draft(
    payload: ApprovalDraftPrepareRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: AIApprovalDraftProvider,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> ApprovalDraftPrepareResponse:
    """
    자연어 요청을 일반·출장·경비 양식으로 정리합니다. 정보가 부족하면
    추가 질문을, 충분하면 저장 전 미리보기를 반환합니다. 이 단계에서는
    결재 문서를 저장하지 않습니다.
    """
    return approval_draft_service.prepare_approval_draft(
        db,
        current_employee,
        payload,
        provider,
        embedding_provider,
    )


@router.post(
    "/confirm", response_model=ApprovalRead, status_code=201, summary="AI 결재 초안 저장 확인"
)
def confirm_approval_draft(
    payload: ApprovalDraftConfirmRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """
    사용자가 확인한 미리보기를 초안으로 저장합니다. 확인 토큰이 필요하며
    같은 토큰을 재사용해도 문서는 한 번만 생성됩니다. 제출은 별도
    단계입니다.
    """
    approval = approval_draft_service.confirm_approval_draft(
        db,
        current_employee,
        payload.preview,
        payload.confirmation_token,
    )
    return approval_read(approval)

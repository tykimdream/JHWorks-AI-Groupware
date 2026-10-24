from fastapi import APIRouter

from app.api.dependencies import CurrentEmployee, DbSession, PolicyEmbeddingProviderDependency
from app.schemas.approval import ApprovalRead
from app.schemas.leave_draft_tool import (
    LeaveDraftConfirmRequest,
    LeaveDraftPrepareRequest,
    LeaveDraftPrepareResponse,
)
from app.services import leave_draft_tool as leave_draft_tool_service
from app.services.mappers import approval_read

router = APIRouter(prefix="/leave-draft-tool", tags=["근태·휴가"])


@router.post(
    "/prepare", response_model=LeaveDraftPrepareResponse, summary="휴가 초안 미리보기 생성"
)
def prepare_leave_draft(
    payload: LeaveDraftPrepareRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> LeaveDraftPrepareResponse:
    """
    선택한 휴가 후보로 저장 전 미리보기와 확인 토큰을 생성합니다. 이
    단계에서는 결재 문서를 저장하지 않습니다.
    """
    return leave_draft_tool_service.prepare_leave_draft(
        db,
        current_employee,
        payload,
        embedding_provider,
    )


@router.post(
    "/confirm", response_model=ApprovalRead, status_code=201, summary="휴가 초안 저장 확인"
)
def confirm_leave_draft(
    payload: LeaveDraftConfirmRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """
    확인 토큰을 검증하고 휴가 초안을 한 번만 저장합니다. 제출은 별도
    확인이 필요합니다.
    """
    approval = leave_draft_tool_service.confirm_leave_draft(
        db,
        current_employee,
        payload.preview,
        payload.confirmation_token,
    )
    return approval_read(approval)

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

router = APIRouter(prefix="/leave-draft-tool", tags=["leave-draft-tool"])


@router.post("/prepare", response_model=LeaveDraftPrepareResponse)
def prepare_leave_draft(
    payload: LeaveDraftPrepareRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> LeaveDraftPrepareResponse:
    return leave_draft_tool_service.prepare_leave_draft(
        db,
        current_employee,
        payload,
        embedding_provider,
    )


@router.post("/confirm", response_model=ApprovalRead, status_code=201)
def confirm_leave_draft(
    payload: LeaveDraftConfirmRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    approval = leave_draft_tool_service.confirm_leave_draft(
        db,
        current_employee,
        payload.preview,
        payload.confirmation_token,
    )
    return approval_read(approval)

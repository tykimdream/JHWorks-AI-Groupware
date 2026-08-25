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

router = APIRouter(prefix="/approval-draft-assistant", tags=["approval-draft-assistant"])


@router.post("/prepare", response_model=ApprovalDraftPrepareResponse)
def prepare_approval_draft(
    payload: ApprovalDraftPrepareRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: AIApprovalDraftProvider,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> ApprovalDraftPrepareResponse:
    return approval_draft_service.prepare_approval_draft(
        db,
        current_employee,
        payload,
        provider,
        embedding_provider,
    )


@router.post("/confirm", response_model=ApprovalRead, status_code=201)
def confirm_approval_draft(
    payload: ApprovalDraftConfirmRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    approval = approval_draft_service.confirm_approval_draft(
        db,
        current_employee,
        payload.preview,
        payload.confirmation_token,
    )
    return approval_read(approval)

from typing import Literal

from fastapi import APIRouter, Query

from app.api.dependencies import (
    AIReviewProvider,
    CurrentEmployee,
    DbSession,
    PolicyEmbeddingProviderDependency,
)
from app.models.enums import ApprovalStatus
from app.schemas.ai_review import AIReviewRequest, AIReviewResponse
from app.schemas.approval import (
    ApprovalCommand,
    ApprovalCreate,
    ApprovalDecision,
    ApprovalListResponse,
    ApprovalRead,
    ApprovalUpdate,
)
from app.services import approval as approval_service
from app.services import approval_review as approval_review_service
from app.services.mappers import approval_read

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=ApprovalListResponse)
def list_approvals(
    db: DbSession,
    current_employee: CurrentEmployee,
    scope: Literal["mine", "assigned"] = Query(default="mine"),
) -> ApprovalListResponse:
    items = approval_service.list_approvals(db, current_employee, scope)
    return ApprovalListResponse(items=[approval_read(item) for item in items], total=len(items))


@router.post("", response_model=ApprovalRead, status_code=201)
def create_approval(
    payload: ApprovalCreate,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    return approval_read(approval_service.create_draft(db, current_employee, payload))


@router.get("/{approval_id}", response_model=ApprovalRead)
def get_approval(
    approval_id: str,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    return approval_read(approval_service.get_approval(db, current_employee, approval_id))


@router.patch("/{approval_id}", response_model=ApprovalRead)
def update_approval(
    approval_id: str,
    payload: ApprovalUpdate,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    return approval_read(approval_service.update_draft(db, current_employee, approval_id, payload))


@router.post("/{approval_id}/submit", response_model=ApprovalRead)
def submit_approval(
    approval_id: str,
    payload: ApprovalCommand,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    return approval_read(
        approval_service.submit_approval(db, current_employee, approval_id, payload.version)
    )


@router.post("/{approval_id}/approve", response_model=ApprovalRead)
def approve_approval(
    approval_id: str,
    payload: ApprovalDecision,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    return approval_read(
        approval_service.decide_approval(
            db,
            current_employee,
            approval_id,
            payload,
            ApprovalStatus.APPROVED,
        )
    )


@router.post("/{approval_id}/reject", response_model=ApprovalRead)
def reject_approval(
    approval_id: str,
    payload: ApprovalDecision,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    return approval_read(
        approval_service.decide_approval(
            db,
            current_employee,
            approval_id,
            payload,
            ApprovalStatus.REJECTED,
        )
    )


@router.post("/{approval_id}/revise", response_model=ApprovalRead)
def revise_approval(
    approval_id: str,
    payload: ApprovalCommand,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    return approval_read(
        approval_service.revise_approval(db, current_employee, approval_id, payload.version)
    )


@router.post("/{approval_id}/ai-review", response_model=AIReviewResponse)
def review_approval(
    approval_id: str,
    payload: AIReviewRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: AIReviewProvider,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> AIReviewResponse:
    return approval_review_service.review_approval(
        db,
        current_employee,
        approval_id,
        payload.version,
        provider,
        embedding_provider,
    )

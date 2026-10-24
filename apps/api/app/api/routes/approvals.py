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
from app.schemas.expense_checks import ExpenseChecks, ExpenseInsights
from app.services import approval as approval_service
from app.services import approval_review as approval_review_service
from app.services.expense_checks import check_expense, expense_insights
from app.services.mappers import approval_read

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=ApprovalListResponse)
def list_approvals(
    db: DbSession,
    current_employee: CurrentEmployee,
    scope: Literal["mine", "assigned"] = Query(default="mine"),
) -> ApprovalListResponse:
    """내 문서 또는 나에게 배정된 문서를 조회합니다. 서버 권한 필터 이후의 목록만 반환합니다."""
    items = approval_service.list_approvals(db, current_employee, scope)
    return ApprovalListResponse(items=[approval_read(item) for item in items], total=len(items))


@router.post("", response_model=ApprovalRead, status_code=201)
def create_approval(
    payload: ApprovalCreate,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """미완성 정보를 허용하는 DRAFT 저장입니다. 제출·결재선 생성은 별도 명령입니다."""
    return approval_read(approval_service.create_draft(db, current_employee, payload))


@router.get("/expense-insights", response_model=ExpenseInsights)
def get_expense_insights(db: DbSession, current_employee: CurrentEmployee) -> ExpenseInsights:
    """내 최근 초안·결재 중 경비 10개를 점검해 누락·중복 후보가 있는 문서만 반환합니다."""
    return expense_insights(db, current_employee)


@router.get("/{approval_id}/expense-checks", response_model=ExpenseChecks)
def get_expense_checks(
    approval_id: str,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ExpenseChecks:
    """조회 권한이 있는 경비의 필수 정보와 동일 지출 후보를 점검합니다.

    원본 영수증 검증이 아닙니다.
    """
    return check_expense(db, current_employee, approval_id)


@router.get("/{approval_id}", response_model=ApprovalRead)
def get_approval(
    approval_id: str,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """작성자/배정 결재자·체험 공간 범위를 검증한 뒤 문서를 조회합니다."""
    return approval_read(approval_service.get_approval(db, current_employee, approval_id))


@router.patch("/{approval_id}", response_model=ApprovalRead)
def update_approval(
    approval_id: str,
    payload: ApprovalUpdate,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """현재 버전의 초안을 수정합니다. 오래된 version 또는 수정 불가 상태는 거부합니다."""
    return approval_read(approval_service.update_draft(db, current_employee, approval_id, payload))


@router.post("/{approval_id}/submit", response_model=ApprovalRead)
def submit_approval(
    approval_id: str,
    payload: ApprovalCommand,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """필수 정보·직속 관리자·version을 재검증하고 결재선을 생성해 PENDING으로 전환합니다."""
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
    """현재 배정 결재자만 승인합니다. 휴가이면 연차 예약을 사용으로 확정합니다."""
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
    """현재 배정 결재자가 사유와 함께 반려합니다. 휴가이면 예약 연차를 복원합니다."""
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
    """작성자가 반려 문서를 DRAFT로 되돌립니다. 이전 결재 회차 이력은 보존합니다."""
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
    """서버 규칙 검사와 정책 근거·모델 검토를 결합합니다. 공개 AI 비활성 시 사용할 수 없습니다."""
    return approval_review_service.review_approval(
        db,
        current_employee,
        approval_id,
        payload.version,
        provider,
        embedding_provider,
    )

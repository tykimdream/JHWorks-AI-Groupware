from typing import Literal

from fastapi import APIRouter, Query

from app.api.dependencies import (
    AIApprovalDraftProvider,
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
    ApprovalSummary,
    ApprovalSummaryPage,
    ApprovalUpdate,
)
from app.schemas.expense_checks import ExpenseChecks, ExpenseInsights
from app.schemas.expense_guide import ExpenseGuide
from app.schemas.expense_revision import (
    ExpenseDecisionBrief,
    ExpenseRevisionApply,
    ExpenseRevisionRequest,
    ExpenseRevisionResponse,
)
from app.services import approval as approval_service
from app.services import approval_review as approval_review_service
from app.services import expense_revision
from app.services.expense_checks import check_expense, expense_insights
from app.services.expense_guide import expense_guide
from app.services.mappers import approval_read, employee_summary

router = APIRouter(prefix="/approvals", tags=["전자결재"])


@router.get("", response_model=ApprovalListResponse, summary="결재 목록 조회")
def list_approvals(
    db: DbSession,
    current_employee: CurrentEmployee,
    scope: Literal["mine", "assigned"] = Query(default="mine"),
) -> ApprovalListResponse:
    """내가 작성한 문서 또는 나에게 결재가 배정된 문서를 조회합니다."""
    items = approval_service.list_approvals(db, current_employee, scope)
    return ApprovalListResponse(items=[approval_read(item) for item in items], total=len(items))


@router.get("/summaries", response_model=ApprovalSummaryPage, summary="결재 목록 요약 조회")
def list_approval_summaries(
    db: DbSession,
    current_employee: CurrentEmployee,
    scope: Literal["mine", "assigned"] = Query(default="mine"),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=10000),
    status: ApprovalStatus | None = None,
) -> ApprovalSummaryPage:
    """열람 범위 내 요약을 최근 수정순으로 반환합니다. 페이지 간 변경은 스냅샷이 아닙니다."""
    rows, total = approval_service.list_approval_page(
        db, current_employee, scope, limit, offset, status
    )
    items = [
        ApprovalSummary(
            id=item.id, type=item.type, title=item.title,
            content_preview=item.content[:200], author=employee_summary(item.author),
            status=item.status, amount=item.amount,
            leave_days=item.details.get("requestedDays") if item.type.value == "LEAVE" else None,
            line_count=len(item.lines), updated_at=item.updated_at,
        )
        for item in rows
    ]
    return ApprovalSummaryPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=ApprovalRead, status_code=201, summary="결재 초안 저장")
def create_approval(
    payload: ApprovalCreate,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """
    일반·출장·경비·휴가 양식의 초안을 저장합니다. 일부 항목이 비어
    있어도 저장할 수 있으며, 제출은 별도로 실행합니다.
    """
    return approval_read(approval_service.create_draft(db, current_employee, payload))


@router.get("/expense-insights", response_model=ExpenseInsights, summary="보완이 필요한 경비 조회")
def get_expense_insights(db: DbSession, current_employee: CurrentEmployee) -> ExpenseInsights:
    """
    내 초안·결재 중인 경비를 최근 10개까지 점검하고, 누락 정보나
    중복 후보가 있는 문서를 반환합니다.
    """
    return expense_insights(db, current_employee)


@router.get(
    "/{approval_id}/expense-checks",
    response_model=ExpenseChecks,
    summary="경비 누락·중복 후보 확인",
)
def get_expense_checks(
    approval_id: str,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ExpenseChecks:
    """
    열람 가능한 경비 문서의 필수 항목과 같은 지출일·사용처·금액의
    문서를 확인합니다. 영수증 원본이나 실제 중복 지출을 판정하지는
    않습니다.
    """
    return check_expense(db, current_employee, approval_id)


@router.get(
    "/expense-guide", response_model=ExpenseGuide, summary="경비 단계·필수값·자주 묻는 질문"
)
def get_expense_guide(current_employee: CurrentEmployee) -> ExpenseGuide:
    """로그인한 사용자에게 서버 경비 계약 기반 안내를 제공합니다.
    문서 변경과 모델 호출은 없습니다."""
    return expense_guide()


@router.get("/{approval_id}", response_model=ApprovalRead, summary="결재 상세 조회")
def get_approval(
    approval_id: str,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """
    문서 내용, 현재 상태, 버전과 결재 이력을 조회합니다. 작성자 또는
    지정 결재자만 열람할 수 있습니다.
    """
    return approval_read(approval_service.get_approval(db, current_employee, approval_id))


@router.patch("/{approval_id}", response_model=ApprovalRead, summary="결재 초안 수정")
def update_approval(
    approval_id: str,
    payload: ApprovalUpdate,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """
    작성자가 초안을 수정합니다. 요청의 version이 현재 버전과
    다르면 변경하지 않습니다.
    """
    return approval_read(approval_service.update_draft(db, current_employee, approval_id, payload))


@router.post("/{approval_id}/submit", response_model=ApprovalRead, summary="결재 제출")
def submit_approval(
    approval_id: str,
    payload: ApprovalCommand,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """
    필수 항목과 현재 직속 관리자를 확인한 뒤 초안을 결재 대기 상태로
    전환합니다. 작성자만 실행할 수 있습니다.
    """
    return approval_read(
        approval_service.submit_approval(db, current_employee, approval_id, payload.version)
    )


@router.post("/{approval_id}/approve", response_model=ApprovalRead, summary="결재 승인")
def approve_approval(
    approval_id: str,
    payload: ApprovalDecision,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """
    현재 지정된 결재자가 대기 중인 문서를 승인합니다. 휴가 문서는
    예약된 연차를 사용 처리합니다.
    """
    return approval_read(
        approval_service.decide_approval(
            db,
            current_employee,
            approval_id,
            payload,
            ApprovalStatus.APPROVED,
        )
    )


@router.post("/{approval_id}/reject", response_model=ApprovalRead, summary="결재 반려")
def reject_approval(
    approval_id: str,
    payload: ApprovalDecision,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """
    현재 지정된 결재자가 사유를 입력해 문서를 반려합니다. 휴가 문서는
    예약된 연차를 돌려줍니다.
    """
    return approval_read(
        approval_service.decide_approval(
            db,
            current_employee,
            approval_id,
            payload,
            ApprovalStatus.REJECTED,
        )
    )


@router.post("/{approval_id}/revise", response_model=ApprovalRead, summary="반려 문서 재작성")
def revise_approval(
    approval_id: str,
    payload: ApprovalCommand,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """
    작성자가 반려 문서를 수정 가능한 초안으로 전환합니다. 이전 결재
    회차와 의견은 보존합니다.
    """
    return approval_read(
        approval_service.revise_approval(db, current_employee, approval_id, payload.version)
    )


@router.post(
    "/{approval_id}/ai-review", response_model=AIReviewResponse, summary="AI로 결재 문서 검토"
)
def review_approval(
    approval_id: str,
    payload: AIReviewRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: AIReviewProvider,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> AIReviewResponse:
    """
    문서의 누락 정보와 정책 근거를 검토합니다. 문서를 자동 수정하거나
    제출하지 않습니다. 공개 데모에서는 AI 호출이 비활성화되어
    있습니다.
    """
    return approval_review_service.review_approval(
        db,
        current_employee,
        approval_id,
        payload.version,
        provider,
        embedding_provider,
    )


@router.get(
    "/{approval_id}/decision-brief",
    response_model=ExpenseDecisionBrief,
    summary="결재자 경비 검토 근거",
)
def get_decision_brief(
    approval_id: str, db: DbSession, current_employee: CurrentEmployee, version: int = Query(ge=1)
) -> ExpenseDecisionBrief:
    """현재 결재자에게 문서 버전·중복 후보·규정 원문 기준을 제공합니다.
    AI 호출이나 승인 판정은 없습니다."""
    return expense_revision.decision_brief(db, current_employee, approval_id, version)


@router.post(
    "/{approval_id}/expense-revision/prepare",
    response_model=ExpenseRevisionResponse,
    summary="반려 경비 AI 수정 제안 준비",
)
def prepare_expense_revision(
    approval_id: str,
    payload: ExpenseRevisionRequest,
    db: DbSession,
    current_employee: CurrentEmployee,
    provider: AIApprovalDraftProvider,
    embedding_provider: PolicyEmbeddingProviderDependency,
) -> ExpenseRevisionResponse:
    """작성자의 기존 필드와 추가 답변만 지출 근거로 사용합니다.
    반려 의견은 수정 요청이며 사실 근거가 아닙니다.
    문서를 변경하지 않고 질문 또는 변경 전후를 반환합니다. 공개 데모에서는 비활성화됩니다."""
    return expense_revision.prepare_revision(
        db, current_employee, approval_id, payload, provider, embedding_provider
    )


@router.post(
    "/{approval_id}/expense-revision/apply",
    response_model=ApprovalRead,
    summary="확인한 경비 수정 제안을 같은 문서의 초안에 반영",
)
def apply_expense_revision(
    approval_id: str,
    payload: ExpenseRevisionApply,
    db: DbSession,
    current_employee: CurrentEmployee,
) -> ApprovalRead:
    """작성자·버전·제안 서명·규정 변경을 검사하고 초안으로 전환합니다.
    반려 이력을 보존하며 제출하지 않습니다.
    성공 후 재요청은 버전 충돌을 반환하므로 최신 문서를 조회하세요."""
    return approval_read(
        expense_revision.apply_revision(db, current_employee, approval_id, payload)
    )

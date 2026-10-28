import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import TypedDict, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.approval_draft import (
    PROMPT_VERSION,
    REVISION_PROMPT_VERSION,
    ApprovalDraftCandidate,
    ApprovalDraftProvider,
    ApprovalDraftProviderError,
    ApprovalDraftProviderInput,
    DraftIntent,
    DraftProviderResult,
)
from app.ai.policy_embedding import PolicyEmbeddingProvider
from app.core.config import get_settings
from app.core.errors import (
    AppError,
    AuthorizationError,
    ConflictError,
    DomainValidationError,
    ServiceUnavailableError,
)
from app.core.security import (
    create_approval_draft_confirmation_token,
    decode_approval_draft_confirmation_token,
)
from app.models.approval import Approval
from app.models.employee import Employee
from app.models.enums import ApprovalStatus, ApprovalType
from app.schemas.approval import (
    ApprovalCreate,
    BusinessTripDetails,
    CostBreakdown,
    ExpenseDetails,
    GeneralDetails,
)
from app.schemas.approval_draft_ai import (
    ApprovalDraftAIStatus,
    ApprovalDraftCandidateRead,
    ApprovalDraftPrepareRequest,
    ApprovalDraftPrepareResponse,
    ApprovalDraftQuestion,
    ApprovalDraftUsage,
)
from app.schemas.draft_execution import DraftStage, DraftStageOutcome
from app.schemas.expense_policy import ExpensePolicyValidation
from app.schemas.policy import (
    PolicyEmbeddingUsage,
    PolicyRetrievalStatus,
    PolicySearchResponse,
)
from app.services import approval as approval_service
from app.services import policy_retrieval
from app.services.draft_execution import DraftExecution
from app.services.expense_grounding import check_expense_input
from app.services.expense_policy import expense_policy_fingerprint, validate_expense_policy
from app.services.expense_validation import expense_validation_errors

QUESTION_PROMPTS = {
    "title": "결재 제목에 반드시 드러나야 할 핵심 업무는 무엇인가요?",
    "content": "결재 목적과 기대 결과를 조금 더 설명해주세요.",
    "details.destination": "출장지는 어디인가요?",
    "details.startDate": "출장 시작일은 언제인가요?",
    "details.endDate": "출장 종료일은 언제인가요?",
    "details.clientName": "관련 고객사 또는 행사명은 무엇인가요?",
    "details.visitPurpose": "이번 출장에서 수행할 업무와 목적은 무엇인가요?",
    "details.costBreakdown": ("예상 비용을 교통비, 숙박비, 식비, 기타 비용으로 나눠 알려주세요."),
    "amount": "예상 비용 총액은 얼마인가요?",
    "amountConsistency": "예상 총액과 비용 항목의 합계가 다릅니다. 정확한 금액을 알려주세요.",
    "details.endDateOrder": "종료일이 시작일보다 빠릅니다. 출장 기간을 다시 알려주세요.",
    "details.expenseDate": "실제로 지출한 날짜는 언제인가요? 미래 날짜는 정산할 수 없습니다.",
    "details.merchant": "어느 사용처에 지출했나요? 상호 또는 결제 대상을 알려주세요.",
    "details.category": "교통비·숙박비·식비·기타 중 어떤 지출인가요?",
    "details.purpose": "어떤 업무를 위해 지출했나요?",
    "details.receiptReference": "증빙 참조를 원문 그대로 알려주세요. 예: 증빙 참조: RCP-001",
    "expenseAmount": "실제로 지출한 금액을 0원보다 큰 원화 금액으로 알려주세요.",
}


def _not_applicable_policy_context() -> PolicySearchResponse:
    return PolicySearchResponse(
        status=PolicyRetrievalStatus.NOT_APPLICABLE,
        items=[],
        provider=None,
        model=None,
        usage=PolicyEmbeddingUsage(input_tokens=0, total_tokens=0),
        latency_ms=0,
    )


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_candidate(candidate: ApprovalDraftCandidate) -> ApprovalDraftCandidate:
    text_fields = (
        "title",
        "content",
        "destination",
        "client_name",
        "visit_purpose",
        "merchant",
        "expense_purpose",
        "receipt_reference",
    )
    updates: dict[str, object] = {
        field: _clean_text(getattr(candidate, field)) for field in text_fields
    }
    breakdown = (
        candidate.transportation,
        candidate.lodging,
        candidate.meals,
        candidate.other,
    )
    if (
        candidate.intent == DraftIntent.BUSINESS_TRIP
        and candidate.amount is None
        and any(value is not None for value in breakdown)
    ):
        updates["amount"] = sum(value or 0 for value in breakdown)
    return candidate.model_copy(update=updates)


def _candidate_read(candidate: ApprovalDraftCandidate) -> ApprovalDraftCandidateRead:
    return ApprovalDraftCandidateRead(**candidate.model_dump())


def _expense_details(candidate: ApprovalDraftCandidate) -> ExpenseDetails:
    return ExpenseDetails(
        expense_date=candidate.expense_date,
        merchant=candidate.merchant,
        category=candidate.expense_category,
        purpose=candidate.expense_purpose,
        receipt_reference=candidate.receipt_reference,
    )


def _missing_fields(candidate: ApprovalDraftCandidate) -> list[str]:
    missing: list[str] = []
    for field in ("title", "content"):
        if getattr(candidate, field) is None:
            missing.append(field)

    if candidate.intent == DraftIntent.EXPENSE:
        errors = expense_validation_errors(
            _expense_details(candidate).model_dump(mode="json", by_alias=True),
            candidate.amount,
        )
        return missing + ["expenseAmount" if key == "amount" else key for key in errors]

    if candidate.intent != DraftIntent.BUSINESS_TRIP:
        return missing

    required = (
        ("destination", "details.destination"),
        ("start_date", "details.startDate"),
        ("end_date", "details.endDate"),
        ("client_name", "details.clientName"),
        ("visit_purpose", "details.visitPurpose"),
    )
    for attribute, field in required:
        if getattr(candidate, attribute) is None:
            missing.append(field)

    breakdown = (
        candidate.transportation,
        candidate.lodging,
        candidate.meals,
        candidate.other,
    )
    has_breakdown = any(value is not None for value in breakdown)
    if not has_breakdown:
        missing.append("details.costBreakdown")
    if candidate.amount is None:
        missing.append("amount")
    elif has_breakdown and sum(value or 0 for value in breakdown) != candidate.amount:
        missing.append("amountConsistency")

    if (
        candidate.start_date is not None
        and candidate.end_date is not None
        and candidate.start_date > candidate.end_date
    ):
        missing.append("details.endDateOrder")
    return missing


def _preview(candidate: ApprovalDraftCandidate) -> ApprovalCreate:
    if candidate.title is None or candidate.content is None:
        raise ValueError("candidate is not ready")
    if candidate.intent == DraftIntent.GENERAL:
        return ApprovalCreate(
            type=ApprovalType.GENERAL,
            title=candidate.title,
            content=candidate.content,
            amount=candidate.amount,
            details=GeneralDetails(),
            attachment_metadata=[],
        )
    if candidate.intent == DraftIntent.EXPENSE:
        return ApprovalCreate(
            type=ApprovalType.EXPENSE,
            title=candidate.title,
            content=candidate.content,
            amount=candidate.amount,
            details=_expense_details(candidate),
            attachment_metadata=[],
        )
    if candidate.intent != DraftIntent.BUSINESS_TRIP:
        raise ValueError("candidate intent is not supported")
    if any(
        value is None
        for value in (
            candidate.destination,
            candidate.start_date,
            candidate.end_date,
            candidate.client_name,
            candidate.visit_purpose,
            candidate.amount,
        )
    ):
        raise ValueError("candidate is not ready")
    return ApprovalCreate(
        type=ApprovalType.BUSINESS_TRIP,
        title=candidate.title,
        content=candidate.content,
        amount=candidate.amount,
        details=BusinessTripDetails(
            destination=candidate.destination,
            start_date=candidate.start_date,
            end_date=candidate.end_date,
            cost_breakdown=CostBreakdown(
                transportation=candidate.transportation,
                lodging=candidate.lodging,
                meals=candidate.meals,
                other=candidate.other,
            ),
            client_name=candidate.client_name,
            visit_purpose=candidate.visit_purpose,
        ),
        attachment_metadata=[],
    )


def preview_hash(preview: ApprovalCreate) -> str:
    canonical = json.dumps(
        preview.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _policy_context(
    db: Session,
    preview: ApprovalCreate,
    provider: PolicyEmbeddingProvider,
) -> PolicySearchResponse:
    if get_settings().public_demo_enabled:
        # The first public capability has no paid embedding or policy-model stage.
        return _not_applicable_policy_context().model_copy(
            update={"status": PolicyRetrievalStatus.UNAVAILABLE}
        )
    policy_type = policy_retrieval.APPROVAL_POLICY_TYPES.get(preview.type)
    if policy_type is None:
        return _not_applicable_policy_context()
    draft = Approval(
        id="preview",
        type=preview.type,
        title=preview.title,
        content=preview.content,
        author_id="preview",
        status=ApprovalStatus.DRAFT,
        amount=preview.amount,
        details=preview.details.model_dump(mode="json", by_alias=True),
        attachment_metadata=[],
    )
    settings = get_settings()
    return policy_retrieval.search_policy_sections(
        db=db,
        query=policy_retrieval.approval_policy_query(draft),
        policy_type=policy_type,
        top_k=settings.policy_retrieval_top_k,
        min_score=settings.policy_retrieval_min_score,
        provider=provider,
        expected_model=settings.policy_embedding_model,
        expected_dimensions=settings.policy_embedding_dimensions,
    )


def _unsupported_message(intent: DraftIntent) -> str:
    if intent == DraftIntent.LEAVE:
        return "휴가 요청은 근태·휴가 화면에서 일정과 연차를 확인한 뒤 준비할 수 있습니다."
    return "현재 요청을 일반 결재 또는 출장 신청으로 안전하게 분류하지 못했습니다."


def prepare_approval_draft(
    db: Session,
    actor: Employee,
    payload: ApprovalDraftPrepareRequest,
    provider: ApprovalDraftProvider,
    embedding_provider: PolicyEmbeddingProvider,
    *,
    revision_context: str | None = None,
    issue_confirmation: bool = True,
) -> ApprovalDraftPrepareResponse:
    execution = DraftExecution(REVISION_PROMPT_VERSION if revision_context else PROMPT_VERSION)
    try:
        result = _execute_prepare(
            db,
            actor,
            payload,
            provider,
            embedding_provider,
            execution,
            revision_context,
            issue_confirmation,
        )
        result.execution = execution.finish(result.status.value)
        return result
    except Exception as exc:
        trace = execution.finish("FAILED")
        error = (
            exc
            if isinstance(exc, AppError)
            else ServiceUnavailableError(
                "AI_DRAFT_EXECUTION_FAILED",
                "AI draft could not be validated. No approval was created.",
            )
        )
        error.details = {
            **(error.details or {}),
            "execution": trace.model_dump(mode="json", by_alias=True),
        }
        if error is exc:
            raise
        raise error from exc


def _execute_prepare(
    db: Session,
    actor: Employee,
    payload: ApprovalDraftPrepareRequest,
    provider: ApprovalDraftProvider,
    embedding_provider: PolicyEmbeddingProvider,
    execution: DraftExecution,
    revision_context: str | None = None,
    issue_confirmation: bool = True,
) -> ApprovalDraftPrepareResponse:
    class GraphState(TypedDict, total=False):
        provider_input: ApprovalDraftProviderInput
        provider_result: DraftProviderResult
        result: ApprovalDraftPrepareResponse

    def extract(state: GraphState) -> GraphState:
        del state
        with execution.stage(DraftStage.INPUT):
            provider_input = ApprovalDraftProviderInput(
                request=payload.request.strip(),
                answers=[answer.strip() for answer in payload.answers if answer.strip()],
                current_date=datetime.now(ZoneInfo("Asia/Seoul")).date(),
                timezone="Asia/Seoul",
                revision_context=revision_context,
            )
            if len(provider_input.request) < 2:
                raise DomainValidationError(
                    "INVALID_DRAFT_REQUEST", "Enter a non-empty draft request."
                )
            safety_identifier = hashlib.sha256(actor.id.encode()).hexdigest()
        with execution.stage(DraftStage.PROVIDER):
            try:
                provider_result = provider.prepare(provider_input, safety_identifier)
                execution.provider_metadata(provider_result.provider, provider_result.model)
            except ApprovalDraftProviderError as exc:
                raise ServiceUnavailableError(
                    "AI_DRAFT_UNAVAILABLE",
                    "AI draft creation is temporarily unavailable. No approval was created.",
                ) from exc
        return {"provider_input": provider_input, "provider_result": provider_result}

    def validate_and_prepare(state: GraphState) -> GraphState:
        provider_input = state["provider_input"]
        provider_result = state["provider_result"]
        with execution.stage(DraftStage.NORMALIZE):
            candidate = _normalize_candidate(
                ApprovalDraftCandidate.model_validate(provider_result.candidate.model_dump())
            )
        preview: ApprovalCreate | None = None
        confirmation_token: str | None = None
        policy_context = _not_applicable_policy_context()
        policy_validation: ExpensePolicyValidation | None = None
        with execution.stage(DraftStage.VALIDATE) as validation:
            candidate, grounding = check_expense_input(candidate, provider_input)
            missing = _missing_fields(candidate)
            field_names = {
                "amount": "expenseAmount",
                "expense_date": "details.expenseDate",
                "merchant": "details.merchant",
                "expense_category": "details.category",
                "expense_purpose": "details.purpose",
                "receipt_reference": "details.receiptReference",
            }
            for check in grounding.checks:
                if check.status == "UNVERIFIED" and field_names[check.field] not in missing:
                    missing.append(field_names[check.field])
            public_expense_only = get_settings().public_demo_enabled
            if (
                public_expense_only and candidate.intent != DraftIntent.EXPENSE
            ) or candidate.intent not in {
                DraftIntent.GENERAL,
                DraftIntent.BUSINESS_TRIP,
                DraftIntent.EXPENSE,
            }:
                status = ApprovalDraftAIStatus.UNSUPPORTED
                validation.outcome = DraftStageOutcome.UNSUPPORTED
                assistant_message = (
                    "공개 AI는 경비 정산만 지원합니다. 출장·일반·휴가는 직접 작성해 주세요."
                    if public_expense_only
                    else _unsupported_message(candidate.intent)
                )
                missing = []
                questions: list[ApprovalDraftQuestion] = []
            elif missing:
                status = ApprovalDraftAIStatus.NEEDS_INPUT
                validation.outcome = DraftStageOutcome.NEEDS_INPUT
                assistant_message = (
                    "초안을 완성하려면 아래 정보를 알려주세요. 한 문장으로 함께 답해도 됩니다."
                )
                formats = {
                    "expenseAmount": "금액: 170000원",
                    "details.expenseDate": "지출일: YYYY-MM-DD",
                    "details.merchant": "사용처: 실제 상호",
                    "details.category": "분류: 교통비",
                    "details.purpose": "목적: 실제 업무 목적",
                    "details.receiptReference": "증빙 참조: 실제 참조 번호",
                }
                unverified = {
                    field_names[check.field]
                    for check in grounding.checks
                    if check.status == "UNVERIFIED"
                }
                questions = [
                    ApprovalDraftQuestion(
                        field=field,
                        prompt=(
                            "입력과 일치하는 값을 확인하지 못했습니다. "
                            f"다음 형식으로 실제 값을 알려주세요: {formats[field]}"
                            if field in unverified
                            else QUESTION_PROMPTS[field]
                        ),
                    )
                    for field in missing
                ]
            else:
                status = ApprovalDraftAIStatus.PREVIEW
                assistant_message = (
                    "JHWorks 양식에 맞춘 미리보기입니다. 내용을 확인한 뒤 Draft로 저장하세요."
                )
                questions = []
                preview = _preview(candidate)
        with execution.stage(DraftStage.POLICY) as policy:
            if preview is None:
                policy.outcome = DraftStageOutcome.NOT_APPLICABLE
            else:
                policy_context = _policy_context(db, preview, embedding_provider)
                if preview.type == ApprovalType.EXPENSE:
                    policy_validation = validate_expense_policy(db, preview, policy_context)
                policy.outcome = (
                    DraftStageOutcome.PASSED
                    if (
                        policy_validation is not None
                        and policy_validation.status == "CATALOG_CHECKED"
                    )
                    or policy_context.status == PolicyRetrievalStatus.READY
                    else DraftStageOutcome.NOT_APPLICABLE
                    if policy_context.status == PolicyRetrievalStatus.NOT_APPLICABLE
                    else DraftStageOutcome.UNAVAILABLE
                )
        with execution.stage(DraftStage.PREVIEW) as preview_stage:
            if preview is None:
                preview_stage.outcome = DraftStageOutcome.NOT_APPLICABLE
            else:
                if issue_confirmation:
                    confirmation_token = create_approval_draft_confirmation_token(
                        actor.id,
                        f"confirm_{uuid4().hex}",
                        preview_hash(preview),
                        policy_validation.fingerprint if policy_validation else None,
                    )
        result = ApprovalDraftPrepareResponse(
            execution=execution.report(status.value),
            grounding=grounding,
            policy_validation=policy_validation,
            status=status,
            assistant_message=assistant_message,
            candidate=_candidate_read(candidate),
            missing_fields=missing,
            questions=questions,
            preview=preview,
            confirmation_token=confirmation_token,
            policy_context=policy_context,
            provider=provider_result.provider,
            model=provider_result.model,
            prompt_version=execution.prompt_version,
            usage=ApprovalDraftUsage(
                input_tokens=provider_result.usage.input_tokens,
                output_tokens=provider_result.usage.output_tokens,
                total_tokens=provider_result.usage.total_tokens,
            ),
            latency_ms=provider_result.latency_ms,
            generated_at=datetime.now(UTC),
        )
        return {"result": result}

    graph = StateGraph(GraphState)
    graph.add_node("extract", extract)
    graph.add_node("validate_and_prepare", validate_and_prepare)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "validate_and_prepare")
    graph.add_edge("validate_and_prepare", END)
    # No graph state or prompt is sent to external tracing.
    with tracing_context(enabled=False):
        result_state = graph.compile().invoke({})
    return cast(ApprovalDraftPrepareResponse, result_state["result"])


def confirm_approval_draft(
    db: Session,
    actor: Employee,
    preview: ApprovalCreate,
    confirmation_token: str,
) -> Approval:
    if get_settings().public_demo_enabled and preview.type != ApprovalType.EXPENSE:
        raise AuthorizationError("Public AI confirmation only supports expense drafts")
    confirmation = decode_approval_draft_confirmation_token(confirmation_token)
    if confirmation.employee_id != actor.id:
        raise AuthorizationError("This approval draft confirmation belongs to another employee")
    actual_hash = preview_hash(preview)
    if not hmac.compare_digest(confirmation.preview_hash, actual_hash):
        raise ConflictError(
            "PREVIEW_CHANGED",
            "The approval preview changed after confirmation was prepared.",
        )
    if preview.type == ApprovalType.EXPENSE:
        existing = db.scalar(
            select(Approval.id).where(
                Approval.source_confirmation_id == confirmation.confirmation_id,
                Approval.author_id == actor.id,
            )
        )
        if existing is None and confirmation.policy_fingerprint != expense_policy_fingerprint(db):
            raise ConflictError(
                "POLICY_CHANGED",
                "Expense policies changed. Prepare the preview again.",
            )
    return approval_service.create_draft(
        db,
        actor,
        preview,
        source_confirmation_id=confirmation.confirmation_id,
    )

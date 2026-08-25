import hashlib
import hmac
import json
import logging
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ai.approval_draft import (
    PROMPT_VERSION,
    ApprovalDraftCandidate,
    ApprovalDraftProvider,
    ApprovalDraftProviderError,
    ApprovalDraftProviderInput,
    DraftIntent,
)
from app.ai.policy_embedding import PolicyEmbeddingProvider
from app.core.config import get_settings
from app.core.errors import AuthorizationError, ConflictError, ServiceUnavailableError
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
from app.schemas.policy import (
    PolicyEmbeddingUsage,
    PolicyRetrievalStatus,
    PolicySearchResponse,
)
from app.services import approval as approval_service
from app.services import policy_retrieval

logger = logging.getLogger("jhworks.approval_draft")

QUESTION_PROMPTS = {
    "title": "결재 제목에 반드시 드러나야 할 핵심 업무는 무엇인가요?",
    "content": "결재 목적과 기대 결과를 조금 더 설명해주세요.",
    "details.destination": "출장지는 어디인가요?",
    "details.startDate": "출장 시작일은 언제인가요?",
    "details.endDate": "출장 종료일은 언제인가요?",
    "details.clientName": "관련 고객사 또는 행사명은 무엇인가요?",
    "details.visitPurpose": "이번 출장에서 수행할 업무와 목적은 무엇인가요?",
    "details.costBreakdown": (
        "예상 비용을 교통비, 숙박비, 식비, 기타 비용으로 나눠 알려주세요."
    ),
    "amount": "예상 비용 총액은 얼마인가요?",
    "amountConsistency": "예상 총액과 비용 항목의 합계가 다릅니다. 정확한 금액을 알려주세요.",
    "details.endDateOrder": "종료일이 시작일보다 빠릅니다. 출장 기간을 다시 알려주세요.",
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
    if candidate.amount is None and any(value is not None for value in breakdown):
        updates["amount"] = sum(value or 0 for value in breakdown)
    return candidate.model_copy(update=updates)


def _candidate_read(candidate: ApprovalDraftCandidate) -> ApprovalDraftCandidateRead:
    return ApprovalDraftCandidateRead(**candidate.model_dump())


def _missing_fields(candidate: ApprovalDraftCandidate) -> list[str]:
    missing: list[str] = []
    for field in ("title", "content"):
        if getattr(candidate, field) is None:
            missing.append(field)

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
    if intent == DraftIntent.EXPENSE:
        return "이미 사용한 비용의 정산 요청은 경비 결재 단계에서 지원할 예정입니다."
    if intent == DraftIntent.LEAVE:
        return (
            "휴가 요청은 일정과 프로젝트 제약을 함께 확인하는 휴가 추천 단계에서 "
            "지원할 예정입니다."
        )
    return "현재 요청을 일반 결재 또는 출장 신청으로 안전하게 분류하지 못했습니다."


def prepare_approval_draft(
    db: Session,
    actor: Employee,
    payload: ApprovalDraftPrepareRequest,
    provider: ApprovalDraftProvider,
    embedding_provider: PolicyEmbeddingProvider,
) -> ApprovalDraftPrepareResponse:
    provider_input = ApprovalDraftProviderInput(
        request=payload.request.strip(),
        answers=[answer.strip() for answer in payload.answers if answer.strip()],
        current_date=date.today(),
        timezone="Asia/Seoul",
    )
    safety_identifier = hashlib.sha256(actor.id.encode()).hexdigest()
    try:
        provider_result = provider.prepare(provider_input, safety_identifier)
    except ApprovalDraftProviderError as exc:
        logger.warning(
            "approval_draft_prepare_failed actor_id=%s prompt_version=%s",
            actor.id,
            PROMPT_VERSION,
        )
        raise ServiceUnavailableError(
            "AI_DRAFT_UNAVAILABLE",
            "AI draft creation is temporarily unavailable. No approval was created.",
        ) from exc

    candidate = _normalize_candidate(provider_result.candidate)
    missing = _missing_fields(candidate)
    preview: ApprovalCreate | None = None
    confirmation_token: str | None = None
    policy_context = _not_applicable_policy_context()
    if candidate.intent not in {DraftIntent.GENERAL, DraftIntent.BUSINESS_TRIP}:
        status = ApprovalDraftAIStatus.UNSUPPORTED
        assistant_message = _unsupported_message(candidate.intent)
        missing = []
        questions: list[ApprovalDraftQuestion] = []
    elif missing:
        status = ApprovalDraftAIStatus.NEEDS_INPUT
        assistant_message = (
            "초안을 완성하려면 아래 정보를 알려주세요. 한 문장으로 함께 답해도 됩니다."
        )
        questions = [
            ApprovalDraftQuestion(field=field, prompt=QUESTION_PROMPTS[field])
            for field in missing
        ]
    else:
        status = ApprovalDraftAIStatus.PREVIEW
        assistant_message = (
            "JHWorks 양식에 맞춘 미리보기입니다. 내용을 확인한 뒤 Draft로 저장하세요."
        )
        questions = []
        preview = _preview(candidate)
        policy_context = _policy_context(db, preview, embedding_provider)
        confirmation_id = f"confirm_{uuid4().hex}"
        confirmation_token = create_approval_draft_confirmation_token(
            actor.id,
            confirmation_id,
            preview_hash(preview),
        )

    logger.info(
        "approval_draft_prepared actor_id=%s intent=%s status=%s missing_fields=%s "
        "provider=%s model=%s prompt_version=%s latency_ms=%s input_tokens=%s output_tokens=%s",
        actor.id,
        candidate.intent.value,
        status.value,
        missing,
        provider_result.provider,
        provider_result.model,
        PROMPT_VERSION,
        provider_result.latency_ms,
        provider_result.usage.input_tokens,
        provider_result.usage.output_tokens,
    )
    return ApprovalDraftPrepareResponse(
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
        prompt_version=PROMPT_VERSION,
        usage=ApprovalDraftUsage(
            input_tokens=provider_result.usage.input_tokens,
            output_tokens=provider_result.usage.output_tokens,
            total_tokens=provider_result.usage.total_tokens,
        ),
        latency_ms=provider_result.latency_ms,
        generated_at=datetime.now(UTC),
    )


def confirm_approval_draft(
    db: Session,
    actor: Employee,
    preview: ApprovalCreate,
    confirmation_token: str,
) -> Approval:
    confirmation = decode_approval_draft_confirmation_token(confirmation_token)
    if confirmation.employee_id != actor.id:
        raise AuthorizationError("This approval draft confirmation belongs to another employee")
    actual_hash = preview_hash(preview)
    if not hmac.compare_digest(confirmation.preview_hash, actual_hash):
        raise ConflictError(
            "PREVIEW_CHANGED",
            "The approval preview changed after confirmation was prepared.",
        )
    return approval_service.create_draft(
        db,
        actor,
        preview,
        source_confirmation_id=confirmation.confirmation_id,
    )

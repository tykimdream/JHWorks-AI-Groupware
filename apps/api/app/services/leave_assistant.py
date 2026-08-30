import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.ai.leave_assistant import (
    PROMPT_VERSION,
    LeaveAssistantCandidate,
    LeaveAssistantIntent,
    LeaveAssistantProvider,
    LeaveAssistantProviderError,
    LeaveAssistantProviderInput,
)
from app.ai.policy_embedding import PolicyEmbeddingProvider
from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.models.employee import Employee
from app.models.enums import LeaveAvailabilityStatus, PolicyType
from app.schemas.attendance import LeaveAvailabilityRead
from app.schemas.leave_assistant import (
    LeaveAssistantQuery,
    LeaveAssistantQuestion,
    LeaveAssistantRequest,
    LeaveAssistantResponse,
    LeaveAssistantStatus,
    LeaveAssistantUsage,
)
from app.schemas.policy import (
    PolicyEmbeddingUsage,
    PolicyRetrievalStatus,
    PolicySearchResponse,
)
from app.services import leave_availability, policy_retrieval

logger = logging.getLogger("jhworks.leave_assistant")
SEOUL = ZoneInfo("Asia/Seoul")

QUESTION_PROMPTS = {
    "searchStart": "언제부터 가능한 날짜를 찾을까요? 실제 날짜나 상대 기간으로 알려주세요.",
    "searchEnd": "언제까지 탐색할까요? 실제 날짜나 월 단위로 알려주세요.",
    "requestedDays": "반차부터 5일까지, 며칠의 연차를 사용하고 싶으신가요?",
    "dateOrder": "탐색 종료일이 시작일보다 빠릅니다. 기간을 다시 알려주세요.",
    "dateRange": "한 번에 최대 93일, 같은 연도 안에서 탐색 기간을 다시 정해주세요.",
    "duration": "희망 일수는 0.5일 또는 1~5일의 정수로 알려주세요.",
}


def _empty_policy_context() -> PolicySearchResponse:
    return PolicySearchResponse(
        status=PolicyRetrievalStatus.NOT_APPLICABLE,
        items=[],
        provider=None,
        model=None,
        usage=PolicyEmbeddingUsage(input_tokens=0, total_tokens=0),
        latency_ms=0,
    )


def _missing_fields(candidate: LeaveAssistantCandidate) -> list[str]:
    missing: list[str] = []
    if candidate.search_start is None:
        missing.append("searchStart")
    if candidate.search_end is None:
        missing.append("searchEnd")
    if candidate.requested_days is None:
        missing.append("requestedDays")
    if candidate.search_start is not None and candidate.search_end is not None:
        if candidate.search_end < candidate.search_start:
            missing.append("dateOrder")
        elif (
            (candidate.search_end - candidate.search_start).days > 92
            or candidate.search_start.year != candidate.search_end.year
        ):
            missing.append("dateRange")
    if (
        candidate.requested_days is not None
        and candidate.requested_days != Decimal("0.5")
        and candidate.requested_days != candidate.requested_days.to_integral()
    ):
        missing.append("duration")
    return missing


def _query(candidate: LeaveAssistantCandidate) -> LeaveAssistantQuery:
    return LeaveAssistantQuery(**candidate.model_dump())


def _questions(missing_fields: list[str]) -> list[LeaveAssistantQuestion]:
    return [
        LeaveAssistantQuestion(field=field, prompt=QUESTION_PROMPTS[field])
        for field in missing_fields
    ]


def _policy_context(
    db: Session,
    candidate: LeaveAssistantCandidate,
    provider: PolicyEmbeddingProvider,
) -> PolicySearchResponse:
    settings = get_settings()
    query = (
        "JHWorks annual leave availability and balance policy. "
        f"Search dates: {candidate.search_start} through {candidate.search_end}. "
        f"Requested leave: {candidate.requested_days} days."
    )
    return policy_retrieval.search_policy_sections(
        db=db,
        query=query,
        policy_type=PolicyType.LEAVE,
        top_k=settings.policy_retrieval_top_k,
        min_score=settings.policy_retrieval_min_score,
        provider=provider,
        expected_model=settings.policy_embedding_model,
        expected_dimensions=settings.policy_embedding_dimensions,
    )


def _date_label(value: date) -> str:
    return f"{value.year}년 {value.month}월 {value.day}일"


def _ready_message(availability: LeaveAvailabilityRead) -> str:
    period = f"{_date_label(availability.range_start)}부터 {_date_label(availability.range_end)}"
    if availability.status == LeaveAvailabilityStatus.INSUFFICIENT_BALANCE:
        available = (
            f"현재 가용 연차는 {availability.leave_balance.available_days}일이고 "
            if availability.leave_balance is not None
            else ""
        )
        return f"{period}까지 확인했습니다. {available}{availability.reasons[0].message}"
    if availability.status in {
        LeaveAvailabilityStatus.NO_CANDIDATE,
        LeaveAvailabilityStatus.ACCOUNT_UNAVAILABLE,
    }:
        return f"{period}까지 확인했습니다. {availability.reasons[0].message}"

    candidate_lines = []
    for item in availability.candidates[:3]:
        dates = ", ".join(_date_label(value) for value in item.work_dates)
        reasons = ", ".join(reason.message for reason in item.reasons)
        status_label = "신청 가능" if item.status.value == "AVAILABLE" else "일정 확인 필요"
        candidate_lines.append(f"{dates} ({status_label}: {reasons})")
    if availability.leave_balance is None:
        raise AssertionError("ready availability must include a leave balance")
    return (
        f"{period}까지 {availability.requested_days}일 연차를 확인했습니다. "
        f"현재 가용 연차는 {availability.leave_balance.available_days}일입니다. "
        "결정적 일정 계산 결과: " + " / ".join(candidate_lines)
    )


def consult_leave_availability(
    db: Session,
    actor: Employee,
    payload: LeaveAssistantRequest,
    provider: LeaveAssistantProvider,
    embedding_provider: PolicyEmbeddingProvider,
) -> LeaveAssistantResponse:
    current_date = datetime.now(SEOUL).date()
    try:
        provider_result = provider.structure(
            LeaveAssistantProviderInput(
                request=payload.request.strip(),
                answers=[answer.strip() for answer in payload.answers],
                current_date=current_date,
                timezone="Asia/Seoul",
            ),
            safety_identifier=actor.id,
        )
    except LeaveAssistantProviderError as exc:
        logger.warning("leave_assistant_provider_failed actor_id=%s", actor.id)
        raise ServiceUnavailableError(
            "LEAVE_ASSISTANT_UNAVAILABLE",
            "The AI leave assistant is temporarily unavailable",
        ) from exc

    candidate = provider_result.candidate
    common = {
        "query": _query(candidate),
        "provider": provider_result.provider,
        "model": provider_result.model,
        "prompt_version": PROMPT_VERSION,
        "usage": LeaveAssistantUsage(
            input_tokens=provider_result.usage.input_tokens,
            output_tokens=provider_result.usage.output_tokens,
            total_tokens=provider_result.usage.total_tokens,
        ),
        "latency_ms": provider_result.latency_ms,
        "generated_at": datetime.now(UTC),
    }
    if candidate.intent == LeaveAssistantIntent.UNSUPPORTED:
        return LeaveAssistantResponse(
            status=LeaveAssistantStatus.UNSUPPORTED,
            assistant_message="연차 가능일 확인이나 날짜 추천 요청을 알려주세요.",
            missing_fields=[],
            questions=[],
            availability=None,
            policy_context=_empty_policy_context(),
            **common,
        )

    missing_fields = _missing_fields(candidate)
    if missing_fields:
        questions = _questions(missing_fields)
        return LeaveAssistantResponse(
            status=LeaveAssistantStatus.NEEDS_INPUT,
            assistant_message=questions[0].prompt,
            missing_fields=missing_fields,
            questions=questions,
            availability=None,
            policy_context=_empty_policy_context(),
            **common,
        )

    if (
        candidate.search_start is None
        or candidate.search_end is None
        or candidate.requested_days is None
    ):
        raise AssertionError("validated leave candidate is incomplete")
    availability = leave_availability.find_leave_availability(
        db,
        actor,
        candidate.search_start,
        candidate.search_end,
        candidate.requested_days,
        limit=6,
    )
    policy_context = _policy_context(db, candidate, embedding_provider)
    logger.info(
        "leave_assistant_completed actor_id=%s status=%s range=%s..%s requested_days=%s "
        "candidate_count=%s policy_status=%s model=%s prompt_version=%s latency_ms=%s "
        "input_tokens=%s output_tokens=%s",
        actor.id,
        availability.status,
        candidate.search_start,
        candidate.search_end,
        candidate.requested_days,
        len(availability.candidates),
        policy_context.status,
        provider_result.model,
        PROMPT_VERSION,
        provider_result.latency_ms,
        provider_result.usage.input_tokens,
        provider_result.usage.output_tokens,
    )
    return LeaveAssistantResponse(
        status=LeaveAssistantStatus.READY,
        assistant_message=_ready_message(availability),
        missing_fields=[],
        questions=[],
        availability=availability,
        policy_context=policy_context,
        **common,
    )

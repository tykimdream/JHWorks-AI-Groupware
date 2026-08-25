import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai.policy_embedding import PolicyEmbeddingProvider
from app.ai.work_assistant import (
    PROMPT_VERSION,
    WorkAssistantProvider,
    WorkAssistantProviderError,
)
from app.core.errors import ServiceUnavailableError
from app.models.employee import Employee
from app.schemas.policy import PolicyCitation
from app.schemas.work_assistant import (
    WorkAssistantRequest,
    WorkAssistantResponse,
    WorkAssistantToolExecution,
    WorkAssistantUsage,
)
from app.services.enterprise_tools import ReadOnlyEnterpriseToolExecutor

logger = logging.getLogger("jhworks.work_assistant")


def _policy_citations(
    executions: list[WorkAssistantToolExecution],
) -> list[PolicyCitation]:
    citations: dict[str, PolicyCitation] = {}
    for execution in executions:
        if execution.name != "search_company_policy":
            continue
        raw_items = execution.result.get("items")
        if not isinstance(raw_items, list):
            continue
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            citation = PolicyCitation.model_validate(raw)
            citations[citation.citation_key] = citation
    return list(citations.values())


def answer_work_question(
    db: Session,
    actor: Employee,
    payload: WorkAssistantRequest,
    provider: WorkAssistantProvider,
    embedding_provider: PolicyEmbeddingProvider,
) -> WorkAssistantResponse:
    executor = ReadOnlyEnterpriseToolExecutor(db, actor, embedding_provider)
    safety_identifier = hashlib.sha256(actor.id.encode()).hexdigest()
    try:
        result = provider.answer(payload.message.strip(), executor, safety_identifier)
    except WorkAssistantProviderError as exc:
        logger.warning(
            "work_assistant_failed actor_id=%s prompt_version=%s",
            actor.id,
            PROMPT_VERSION,
        )
        raise ServiceUnavailableError(
            "WORK_ASSISTANT_UNAVAILABLE",
            "The work assistant is temporarily unavailable. No data was changed.",
        ) from exc

    executions = [
        WorkAssistantToolExecution(
            name=execution.name,
            arguments=execution.arguments,
            result=execution.result,
        )
        for execution in result.executions
    ]
    logger.info(
        "work_assistant_completed actor_id=%s tools=%s provider=%s model=%s "
        "prompt_version=%s rounds=%s latency_ms=%s input_tokens=%s output_tokens=%s",
        actor.id,
        [execution.name for execution in executions],
        result.provider,
        result.model,
        PROMPT_VERSION,
        result.round_count,
        result.latency_ms,
        result.usage.input_tokens,
        result.usage.output_tokens,
    )
    return WorkAssistantResponse(
        answer=result.answer.strip(),
        tool_executions=executions,
        policy_citations=_policy_citations(executions),
        provider=result.provider,
        model=result.model,
        prompt_version=PROMPT_VERSION,
        round_count=result.round_count,
        usage=WorkAssistantUsage(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=result.usage.total_tokens,
        ),
        latency_ms=result.latency_ms,
        answered_at=datetime.now(UTC),
    )

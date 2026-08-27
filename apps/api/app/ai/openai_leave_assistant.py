import json
from datetime import date
from decimal import Decimal
from enum import StrEnum
from time import perf_counter

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict

from app.ai.leave_assistant import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    LeaveAssistantCandidate,
    LeaveAssistantIntent,
    LeaveAssistantProviderError,
    LeaveAssistantProviderInput,
    LeaveAssistantProviderResult,
    LeaveAssistantProviderUsage,
)


class LeaveAssistantRequestedDays(StrEnum):
    HALF = "0.5"
    ONE = "1.0"
    TWO = "2.0"
    THREE = "3.0"
    FOUR = "4.0"
    FIVE = "5.0"


class LeaveAssistantStructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: LeaveAssistantIntent
    search_start: date | None
    search_end: date | None
    requested_days: LeaveAssistantRequestedDays | None


def _to_candidate(output: LeaveAssistantStructuredOutput) -> LeaveAssistantCandidate:
    requested_days = (
        Decimal(output.requested_days.value)
        if output.requested_days is not None
        else None
    )
    return LeaveAssistantCandidate(
        intent=output.intent,
        search_start=output.search_start,
        search_end=output.search_end,
        requested_days=requested_days,
    )


class OpenAILeaveAssistantProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self._model = model

    def structure(
        self,
        provider_input: LeaveAssistantProviderInput,
        safety_identifier: str,
    ) -> LeaveAssistantProviderResult:
        started_at = perf_counter()
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=SYSTEM_PROMPT,
                input=[
                    {
                        "role": "user",
                        "content": json.dumps(
                            provider_input.model_dump(mode="json"),
                            ensure_ascii=False,
                        ),
                    }
                ],
                text_format=LeaveAssistantStructuredOutput,
                max_output_tokens=1200,
                prompt_cache_key=PROMPT_VERSION,
                safety_identifier=safety_identifier,
                store=False,
            )
        except OpenAIError as exc:
            raise LeaveAssistantProviderError(
                "The AI leave assistant provider is unavailable"
            ) from exc

        output = response.output_parsed
        if output is None:
            raise LeaveAssistantProviderError(
                "The AI leave assistant provider returned no usable result"
            )
        candidate = _to_candidate(output)
        usage = response.usage
        return LeaveAssistantProviderResult(
            candidate=candidate,
            provider="openai",
            model=response.model or self._model,
            usage=LeaveAssistantProviderUsage(
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
            latency_ms=round((perf_counter() - started_at) * 1000),
        )

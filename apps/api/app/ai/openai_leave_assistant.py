import json
from time import perf_counter

from openai import OpenAI, OpenAIError

from app.ai.leave_assistant import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    LeaveAssistantCandidate,
    LeaveAssistantProviderError,
    LeaveAssistantProviderInput,
    LeaveAssistantProviderResult,
    LeaveAssistantProviderUsage,
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
                text_format=LeaveAssistantCandidate,
                max_output_tokens=500,
                prompt_cache_key=PROMPT_VERSION,
                safety_identifier=safety_identifier,
                store=False,
            )
        except OpenAIError as exc:
            raise LeaveAssistantProviderError(
                "The AI leave assistant provider is unavailable"
            ) from exc

        candidate = response.output_parsed
        if candidate is None:
            raise LeaveAssistantProviderError(
                "The AI leave assistant provider returned no usable result"
            )
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

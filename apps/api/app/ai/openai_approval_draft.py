import json
from time import perf_counter

from openai import OpenAI, OpenAIError

from app.ai.approval_draft import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    ApprovalDraftCandidate,
    ApprovalDraftProviderError,
    ApprovalDraftProviderInput,
    DraftProviderResult,
    DraftProviderUsage,
)


class OpenAIApprovalDraftProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self._client = OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=1,
        )
        self._model = model

    def prepare(
        self,
        provider_input: ApprovalDraftProviderInput,
        safety_identifier: str,
    ) -> DraftProviderResult:
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
                text_format=ApprovalDraftCandidate,
                max_output_tokens=1600,
                prompt_cache_key=PROMPT_VERSION,
                safety_identifier=safety_identifier,
                store=False,
            )
        except OpenAIError as exc:
            raise ApprovalDraftProviderError(
                "The AI approval draft provider is unavailable"
            ) from exc

        candidate = response.output_parsed
        if candidate is None:
            raise ApprovalDraftProviderError(
                "The AI approval draft provider returned no usable result"
            )

        usage = response.usage
        return DraftProviderResult(
            candidate=candidate,
            provider="openai",
            model=response.model or self._model,
            usage=DraftProviderUsage(
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
            latency_ms=round((perf_counter() - started_at) * 1000),
        )

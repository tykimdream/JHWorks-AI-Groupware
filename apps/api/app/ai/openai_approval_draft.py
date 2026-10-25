import json
from time import perf_counter

from openai import OpenAI, OpenAIError, omit

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
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        *,
        max_retries: int = 1,
        standard_tier: bool = False,
    ) -> None:
        self._client = OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
            base_url="https://api.openai.com/v1" if standard_tier else None,
        )
        self._model = model
        self._standard_tier = standard_tier

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
                service_tier="default" if self._standard_tier else omit,
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
            model=response.model if self._standard_tier else (response.model or self._model),
            usage=DraftProviderUsage(
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                known=usage is not None,
            ),
            latency_ms=round((perf_counter() - started_at) * 1000),
            service_tier=response.service_tier,
        )

import json
from time import perf_counter

from openai import OpenAI, OpenAIError

from app.ai.approval_review import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    ApprovalReviewProviderError,
    ProviderReviewResult,
    ProviderUsage,
    ReviewDocument,
    SemanticReviewOutput,
)


class OpenAIApprovalReviewProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self._client = OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=1,
        )
        self._model = model

    def review(self, document: ReviewDocument, safety_identifier: str) -> ProviderReviewResult:
        started_at = perf_counter()
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=SYSTEM_PROMPT,
                input=[
                    {
                        "role": "user",
                        "content": json.dumps(document.model_dump(), ensure_ascii=False),
                    }
                ],
                text_format=SemanticReviewOutput,
                max_output_tokens=2000,
                prompt_cache_key=PROMPT_VERSION,
                safety_identifier=safety_identifier,
                store=False,
            )
        except OpenAIError as exc:
            raise ApprovalReviewProviderError("The AI review provider is unavailable") from exc

        output = response.output_parsed
        if output is None:
            raise ApprovalReviewProviderError("The AI review provider returned no usable result")

        usage = response.usage
        return ProviderReviewResult(
            output=output,
            provider="openai",
            model=response.model or self._model,
            usage=ProviderUsage(
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
            latency_ms=round((perf_counter() - started_at) * 1000),
        )

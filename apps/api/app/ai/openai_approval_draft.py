import json
import re
from time import perf_counter
from typing import Any

from openai import OpenAI, OpenAIError, omit
from pydantic import ValidationError

from app.ai.approval_draft import (
    PROMPT_VERSION,
    REVISION_INSTRUCTIONS,
    REVISION_PROMPT_VERSION,
    SYSTEM_PROMPT,
    ApprovalDraftCandidate,
    ApprovalDraftProviderError,
    ApprovalDraftProviderInput,
    DraftProviderResult,
    DraftProviderUsage,
)


class MaskedApprovalDraftCandidate(ApprovalDraftCandidate):
    amount: int | str | None = None  # type: ignore[assignment]
    transportation: int | str | None = None  # type: ignore[assignment]
    lodging: int | str | None = None  # type: ignore[assignment]
    meals: int | str | None = None  # type: ignore[assignment]
    other: int | str | None = None  # type: ignore[assignment]
    start_date: str | None = None  # type: ignore[assignment]
    end_date: str | None = None  # type: ignore[assignment]
    expense_date: str | None = None  # type: ignore[assignment]


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
        # Fail closed if this adapter is called outside the service masking boundary.
        from app.services.approval_example_corpus import EXAMPLES
        from app.services.draft_privacy import FIELD_NAMES, TOPICS

        inputs = [provider_input.request, *provider_input.answers]
        if provider_input.revision_context:
            inputs.append(provider_input.revision_context)
        allowed_examples = {(title, content) for _, title, content, _ in EXAMPLES}
        if (
            any(re.sub(r"(?:⟦P[0-9]{4}⟧|\s)+", "", value) for value in inputs)
            or any(hint not in TOPICS.values() for hint in provider_input.topic_hints)
            or any(
                key not in FIELD_NAMES.values() or bool(re.sub(r"(?:⟦P[0-9]{4}⟧|\s)+", "", value))
                for key, value in provider_input.field_hints.items()
            )
            or any(
                (example.title, example.content) not in allowed_examples
                for example in provider_input.example_references
            )
        ):
            raise ApprovalDraftProviderError(
                "Unmasked draft input cannot be sent to the AI provider"
            )
        started_at = perf_counter()
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=SYSTEM_PROMPT
                + ("\n" + REVISION_INSTRUCTIONS if provider_input.revision_context else ""),
                input=[
                    {
                        "role": "user",
                        "content": json.dumps(
                            provider_input.model_dump(mode="json", exclude_none=True),
                            ensure_ascii=False,
                        ),
                    }
                ],
                text_format=MaskedApprovalDraftCandidate,
                max_output_tokens=1600,
                prompt_cache_key=REVISION_PROMPT_VERSION
                if provider_input.revision_context
                else PROMPT_VERSION,
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

        # The token map is excluded from the remote request and is only applied here, locally.
        from app.services.draft_privacy import restore_text

        raw: dict[str, Any] = candidate.model_dump()
        for field, value in raw.items():
            if isinstance(value, str):
                raw[field] = restore_text(value, provider_input.private_token_map)
        # Unsupported local conversions become missing fields, not guessed values.
        from datetime import timedelta
        from decimal import Decimal

        for field in ("amount", "transportation", "lodging", "meals", "other"):
            value = raw[field]
            if isinstance(value, str):
                match = re.fullmatch(
                    r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(만)?\s*원?", value.strip()
                )
                if match:
                    number = Decimal(match.group(1).replace(",", "")) * (
                        10000 if match.group(2) else 1
                    )
                    raw[field] = int(number) if number == int(number) else None
                else:
                    raw[field] = None
        for field in ("start_date", "end_date", "expense_date"):
            value = raw[field]
            if isinstance(value, str):
                value = value.strip().rstrip(".,;，；")
                if value == "오늘":
                    raw[field] = provider_input.current_date.isoformat()
                elif value == "어제":
                    raw[field] = (provider_input.current_date - timedelta(days=1)).isoformat()
                else:
                    raw[field] = (
                        value.replace(".", "-")
                        if re.fullmatch(r"\d{4}[-.]\d{2}[-.]\d{2}", value)
                        else None
                    )
        try:
            restored_candidate = ApprovalDraftCandidate.model_validate(raw)
        except ValidationError as exc:
            raise ApprovalDraftProviderError("The AI draft could not be safely restored") from exc

        usage = response.usage
        return DraftProviderResult(
            candidate=restored_candidate,
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

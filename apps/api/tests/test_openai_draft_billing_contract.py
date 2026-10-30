from types import SimpleNamespace
from typing import Any

import pytest

from app.ai import openai_approval_draft
from app.ai.expense_pricing import MODEL
from app.services.draft_privacy import mask_draft_input, restore_text
from tests.test_budgeted_expense_draft import provider_input, result


@pytest.mark.parametrize("known_usage", [True, False])
@pytest.mark.parametrize("revision_context", [None, "목적을 보완하세요. 금액: 999999원"])
def test_public_sdk_parameters_pin_endpoint_tier_and_output_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    known_usage: bool,
    revision_context: str | None,
) -> None:
    constructions: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []

    def parse(**kwargs: Any) -> SimpleNamespace:
        calls.append(kwargs)
        return SimpleNamespace(
            output_parsed=result().candidate,
            model=MODEL if known_usage else "",
            service_tier="default",
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200, total_tokens=1200)
            if known_usage
            else None,
        )

    def client(**kwargs: Any) -> SimpleNamespace:
        constructions.append(kwargs)
        return SimpleNamespace(responses=SimpleNamespace(parse=parse))

    monkeypatch.setattr(openai_approval_draft, "OpenAI", client)
    provider = openai_approval_draft.OpenAIApprovalDraftProvider(
        api_key="synthetic-not-a-key",
        model=MODEL,
        timeout_seconds=20.0,
        max_retries=0,
        standard_tier=True,
    )
    masked = mask_draft_input(
        provider_input().model_copy(update={"revision_context": revision_context})
    ).value
    output = provider.prepare(masked, "opaque")
    assert len(calls) == len(constructions) == 1
    assert constructions[0]["base_url"] == "https://api.openai.com/v1"
    assert constructions[0]["max_retries"] == 0 and constructions[0]["timeout"] == 20.0
    assert calls[0]["model"] == MODEL and calls[0]["service_tier"] == "default"
    assert calls[0]["max_output_tokens"] == 1600 and calls[0]["store"] is False
    assert "tools" not in calls[0] and "previous_response_id" not in calls[0]
    assert output.usage.known is known_usage
    assert output.model == (MODEL if known_usage else "")

    import json

    from app.ai.approval_draft import PROMPT_VERSION, REVISION_PROMPT_VERSION

    supplied = json.loads(calls[0]["input"][0]["content"])
    assert calls[0]["prompt_cache_key"] == (
        REVISION_PROMPT_VERSION if revision_context else PROMPT_VERSION
    )
    if revision_context:
        assert supplied["revision_context"] != revision_context
        assert (
            restore_text(supplied["revision_context"], masked.private_token_map) == revision_context
        )
        assert "NOT expense evidence" in calls[0]["instructions"]
        assert revision_context not in calls[0]["instructions"]
    else:
        assert "revision_context" not in supplied

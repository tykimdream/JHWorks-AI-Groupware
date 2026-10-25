from types import SimpleNamespace
from typing import Any

import pytest

from app.ai import openai_approval_draft
from app.ai.expense_pricing import MODEL
from tests.test_budgeted_expense_draft import provider_input, result


@pytest.mark.parametrize("known_usage", [True, False])
def test_public_sdk_parameters_pin_endpoint_tier_and_output_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    known_usage: bool,
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
    output = provider.prepare(provider_input(), "opaque")
    assert len(calls) == len(constructions) == 1
    assert constructions[0]["base_url"] == "https://api.openai.com/v1"
    assert constructions[0]["max_retries"] == 0 and constructions[0]["timeout"] == 20.0
    assert calls[0]["model"] == MODEL and calls[0]["service_tier"] == "default"
    assert calls[0]["max_output_tokens"] == 1600 and calls[0]["store"] is False
    assert "tools" not in calls[0] and "previous_response_id" not in calls[0]
    assert output.usage.known is known_usage
    assert output.model == (MODEL if known_usage else "")

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

from app.ai.approval_draft import (
    ApprovalDraftCandidate,
    ApprovalDraftProviderError,
    DraftProviderResult,
    DraftProviderUsage,
)
from app.evals.approval_draft import load_cases
from app.ops import expense_model_smoke as smoke


def test_plan_never_loads_credentials_or_constructs_client(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Mock(side_effect=AssertionError("must not load a key in plan mode"))
    client = Mock(side_effect=AssertionError("must not create a client"))
    monkeypatch.setattr(smoke, "get_settings", settings)
    monkeypatch.setattr(smoke, "OpenAIApprovalDraftProvider", client)
    report = smoke.run(execute=False)
    assert report["attempted"] == 0
    assert report["maxRequests"] == 2
    settings.assert_not_called()
    client.assert_not_called()


def test_execution_requires_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smoke, "get_settings", lambda: SimpleNamespace(openai_api_key=None))
    assert smoke.run(execute=True)["status"] == "key-not-configured"


def test_execution_uses_zero_retries_and_stops_after_two(monkeypatch: pytest.MonkeyPatch) -> None:
    cases = {case.id: case for case in load_cases()}
    outputs = []
    for case_id in smoke.CASE_IDS:
        case = cases[case_id]
        candidate = ApprovalDraftCandidate.model_validate(
            {
                "intent": case.expected_intent,
                **case.expected_values,
            }
        )
        outputs.append(
            DraftProviderResult(candidate, "fake", "fake-model", DraftProviderUsage(12, 8, 20), 1)
        )
    provider = Mock()
    provider.prepare.side_effect = outputs
    constructor = Mock(return_value=provider)
    monkeypatch.setattr(smoke, "OpenAIApprovalDraftProvider", constructor)
    monkeypatch.setattr(
        smoke,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key=SecretStr("synthetic-not-a-real-key")),
    )
    report = smoke.run(execute=True)
    assert report["status"] == "passed"
    assert report["attempted"] == provider.prepare.call_count == 2
    assert constructor.call_args.kwargs == {"max_retries": 0}
    assert "synthetic-not-a-real-key" not in str(report)


def test_provider_failure_stops_without_retry_or_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = Mock()
    provider.prepare.side_effect = ApprovalDraftProviderError("sensitive diagnostic")
    monkeypatch.setattr(smoke, "OpenAIApprovalDraftProvider", Mock(return_value=provider))
    monkeypatch.setattr(
        smoke,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key=SecretStr("synthetic-not-a-real-key")),
    )
    report = smoke.run(execute=True)
    assert report["status"] == "provider-failed"
    assert report["attempted"] == provider.prepare.call_count == 1
    assert "sensitive diagnostic" not in str(report)

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import dependencies
from app.core.config import AI_CAPABILITIES, Settings, get_settings


def configured(**updates: Any) -> Settings:
    return Settings(_env_file=None, **{"openai_api_key": "synthetic-not-a-key", **updates})


def test_capabilities_require_allowlist_key_and_global_switch() -> None:
    settings = configured(ai_capabilities=frozenset({"approval_draft"}))
    assert settings.allows_ai("approval_draft")
    assert all(not settings.allows_ai(cap) for cap in AI_CAPABILITIES if cap != "approval_draft")
    assert not configured(ai_enabled=False).allows_ai("approval_draft")
    assert not configured(openai_api_key=None).allows_ai("approval_draft")
    assert not configured(openai_api_key="   ").allows_ai("approval_draft")
    assert not configured(ai_capabilities=frozenset()).allows_ai("approval_draft")
    with pytest.raises(ValidationError):
        configured(ai_capabilities=["unknown_capability"])


@pytest.mark.parametrize(
    ("capability", "factory", "constructor"),
    [
        ("approval_draft", "get_approval_draft_provider", "OpenAIApprovalDraftProvider"),
        ("approval_review", "get_approval_review_provider", "OpenAIApprovalReviewProvider"),
        ("leave_assistant", "get_leave_assistant_provider", "OpenAILeaveAssistantProvider"),
        ("work_assistant", "get_work_assistant_provider", "OpenAIWorkAssistantProvider"),
        ("policy_embedding", "get_policy_embedding_provider", "OpenAIPolicyEmbeddingProvider"),
    ],
)
def test_disabled_provider_cannot_construct_client_even_with_key(
    monkeypatch: pytest.MonkeyPatch, capability: str, factory: str, constructor: str
) -> None:
    settings = configured(ai_capabilities=frozenset())
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    built: list[str] = []
    sentinel = object()

    def construct(**kwargs: Any) -> object:
        built.append(capability)
        return sentinel

    monkeypatch.setattr(dependencies, constructor, construct)
    make: Callable[[], object] = getattr(dependencies, factory)
    assert make() is not sentinel
    assert built == []
    settings.ai_capabilities = frozenset(AI_CAPABILITIES)
    assert make() is sentinel
    assert built == [capability]
    # Public mode closes every real provider even if a runtime mutation bypassed validation.
    settings.public_demo_enabled = True
    assert make() is not sentinel
    assert built == [capability]


def test_configuration_reports_same_capability_contract_without_credentials(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", configured().openai_api_key)
    monkeypatch.setattr(settings, "ai_capabilities", frozenset({"approval_draft"}))
    response = client.get("/api/v1/demo/configuration")
    assert response.status_code == 200
    assert response.json()["aiCapabilities"] == {
        "approvalDraft": True,
        "approvalReview": False,
        "leaveAssistant": False,
        "workAssistant": False,
        "policyEmbedding": False,
    }
    assert "synthetic-not-a-key" not in response.text
    assert "no-store" in response.headers["cache-control"]
    monkeypatch.setattr(settings, "public_demo_enabled", True)
    assert not any(client.get("/api/v1/demo/configuration").json()["aiCapabilities"].values())

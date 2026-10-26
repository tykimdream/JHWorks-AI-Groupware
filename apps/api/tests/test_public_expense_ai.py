from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import DraftIntent, UnavailableApprovalDraftProvider
from app.api import dependencies
from app.core.config import Settings, get_settings
from app.models.ai_budget import AIBudgetCounter
from app.models.approval import Approval
from tests.test_budgeted_expense_draft import SyntheticProvider, result, rollout_limits


@pytest.fixture
def public_expense(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SyntheticProvider, list[dict[str, Any]]]:
    settings = get_settings()
    for name, value in {
        "public_demo_enabled": True,
        "ai_enabled": False,
        "public_expense_ai_enabled": True,
        "public_expense_ai_budget": rollout_limits(scope_day_admissions=1),
        "openai_api_key": Settings(
            _env_file=None, openai_api_key="synthetic-not-a-key"
        ).openai_api_key,
    }.items():
        monkeypatch.setattr(settings, name, value)
    provider = SyntheticProvider()
    constructions: list[dict[str, Any]] = []

    def construct(**kwargs: Any) -> SyntheticProvider:
        constructions.append(kwargs)
        return provider

    monkeypatch.setattr(dependencies, "OpenAIApprovalDraftProvider", construct)
    return provider, constructions


def test_public_flag_requires_explicit_safe_budget_and_never_enables_other_capabilities() -> None:
    values: dict[str, Any] = {
        "public_demo_enabled": True,
        "ai_enabled": False,
        "public_expense_ai_enabled": True,
        "openai_api_key": "synthetic-not-a-key",
    }
    with pytest.raises(ValidationError, match="explicit budget"):
        Settings(_env_file=None, **values)
    config = Settings(_env_file=None, **values, public_expense_ai_budget=rollout_limits())
    assert config.allows_ai("approval_draft")
    assert not any(
        config.allows_ai(cap)
        for cap in ("approval_review", "work_assistant", "leave_assistant", "policy_embedding")
    )
    for overrides in (
        {"month_micro_usd": 2000001},
        {"day_micro_usd": 500001},
        {"day_micro_usd": 307199},
        {"concurrent_requests": 2},
        {"scope_day_admissions": 6},
        {"day_admissions": 11},
    ):
        with pytest.raises(ValidationError, match="rollout limits"):
            Settings(_env_file=None, **values, public_expense_ai_budget=rollout_limits(**overrides))


def test_http_request_uses_server_workspace_budget_across_roles_and_pinned_no_retry_provider(
    client: TestClient,
    session_factory: sessionmaker[Session],
    public_expense: tuple[SyntheticProvider, list[dict[str, Any]]],
) -> None:
    provider, constructions = public_expense
    assert client.get("/api/v1/demo/configuration").json()["expenseAiRequestLimit"] == 1
    assert isinstance(dependencies.get_approval_draft_provider(), UnavailableApprovalDraftProvider)
    assert client.post("/api/v1/demo/start").status_code == 200
    with session_factory() as db:
        before = db.scalar(select(func.count()).select_from(Approval))
    response = client.post(
        "/api/v1/approval-draft-assistant/prepare", json={"request": "CES 경비 17만원 정산"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "NEEDS_INPUT"
    assert response.json()["preview"] is None
    assert provider.calls == 1
    assert constructions[0]["max_retries"] == 0 and constructions[0]["standard_tier"] is True
    assert constructions[0]["model"] == "gpt-5.4-mini-2026-03-17"
    assert client.post("/api/v1/demo/role", json={"role": "manager"}).status_code == 200
    denied = client.post(
        "/api/v1/approval-draft-assistant/prepare", json={"request": "CES 경비 17만원 정산"}
    )
    assert denied.status_code == 429 and denied.json()["error"]["code"] == "AI_BUDGET_EXHAUSTED"
    assert provider.calls == 1 and len(constructions) == 1
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Approval)) == before
        gate = db.get(AIBudgetCounter, "global")
        assert gate is not None and gate.active_requests == 0


def test_public_candidate_cannot_preview_non_expense_intent(
    client: TestClient,
    public_expense: tuple[SyntheticProvider, list[dict[str, Any]]],
) -> None:
    provider, _ = public_expense
    provider.output = result()
    provider.output.candidate.intent = DraftIntent.GENERAL
    assert client.post("/api/v1/demo/start").status_code == 200
    response = client.post(
        "/api/v1/approval-draft-assistant/prepare", json={"request": "일반 결재 초안"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "UNSUPPORTED"
    assert response.json()["preview"] is None and response.json()["confirmationToken"] is None


def test_oversized_answer_is_rejected_before_provider(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    response = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={
            "request": "경비 초안",
            "answers": ["x" * 2001],
        },
    )
    assert response.status_code == 422


def test_public_expense_preview_confirm_submit_and_role_approval_without_paid_policy(
    client: TestClient,
    session_factory: sessionmaker[Session],
    public_expense: tuple[SyntheticProvider, list[dict[str, Any]]],
    fake_embedding_provider: Any,
) -> None:
    from datetime import date

    from app.ai.approval_draft import ApprovalDraftCandidate
    from app.models.enums import ExpenseCategory

    provider, constructions = public_expense
    provider.output = result()
    candidate = ApprovalDraftCandidate(
        intent=DraftIntent.EXPENSE,
        title="Synthetic CES expense",
        content="Synthetic CES transport",
        amount=170000,
        expense_date=date(2026, 8, 24),
        merchant="Synthetic transport",
        expense_category=ExpenseCategory.TRANSPORTATION,
        expense_purpose="Synthetic CES visit",
        receipt_reference="SYNTHETIC-CES-001",
    )

    provider.output = replace(provider.output, candidate=candidate)

    # Even an injected available embedding provider must not be invoked in this capability.
    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Public expense AI must not call embeddings")

    fake_embedding_provider.embed = forbidden
    assert client.post("/api/v1/demo/start").status_code == 200
    with session_factory() as db:
        before = db.scalar(select(func.count()).select_from(Approval))
    prepared = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={
            "request": (
                "금액: 170000원; 지출일: 2026-08-24; 사용처: Synthetic transport; "
                "분류: TRANSPORTATION; 목적: Synthetic CES visit; 증빙 참조: SYNTHETIC-CES-001"
            )
        },
    )
    assert prepared.status_code == 200, prepared.text
    body = prepared.json()
    assert body["status"] == "PREVIEW" and body["policyContext"]["status"] == "UNAVAILABLE"
    assert body["policyContext"]["items"] == []
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Approval)) == before
    payload = {"preview": body["preview"], "confirmationToken": body["confirmationToken"]}
    saved = client.post("/api/v1/approval-draft-assistant/confirm", json=payload)
    assert saved.status_code == 201, saved.text
    replay = client.post("/api/v1/approval-draft-assistant/confirm", json=payload)
    assert replay.status_code == 201 and replay.json()["id"] == saved.json()["id"]
    draft = saved.json()
    submitted = client.post(
        f"/api/v1/approvals/{draft['id']}/submit", json={"version": draft["version"]}
    )
    assert submitted.status_code == 200, submitted.text
    assert client.post("/api/v1/demo/role", json={"role": "manager"}).status_code == 200
    approved = client.post(
        f"/api/v1/approvals/{draft['id']}/approve", json={"version": submitted.json()["version"]}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    assert provider.calls == 1 and len(constructions) == 1

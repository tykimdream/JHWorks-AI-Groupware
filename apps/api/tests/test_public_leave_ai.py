from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.expense_pricing import MODEL
from app.ai.leave_assistant import (
    LeaveAssistantCandidate,
    LeaveAssistantIntent,
    LeaveAssistantProviderInput,
    LeaveAssistantProviderResult,
    LeaveAssistantProviderUsage,
)
from app.api import dependencies
from app.core.config import Settings, get_settings
from app.models.ai_budget import AIBudgetReservation
from tests.test_ai_budget import budget_factory as budget_factory
from tests.test_budgeted_expense_draft import rollout_limits


class SyntheticLeave:
    def __init__(self) -> None:
        self.calls = 0
        self.safety_identifier = ""

    def structure(
        self, value: LeaveAssistantProviderInput, safety_identifier: str
    ) -> LeaveAssistantProviderResult:
        self.calls += 1
        self.safety_identifier = safety_identifier
        return LeaveAssistantProviderResult(
            candidate=LeaveAssistantCandidate(intent=LeaveAssistantIntent.RECOMMEND_DATES),
            provider="synthetic",
            model=MODEL,
            usage=LeaveAssistantProviderUsage(1000, 200, 1200),
            latency_ms=1,
            service_tier="default",
        )


def test_public_leave_uses_shared_budget_and_scoped_factory(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    for key, value in {
        "public_demo_enabled": True,
        "ai_enabled": False,
        "public_expense_ai_enabled": True,
        "public_leave_ai_enabled": True,
        "public_expense_ai_budget": rollout_limits(scope_day_admissions=1),
        "openai_api_key": Settings(_env_file=None, openai_api_key="synthetic").openai_api_key,
    }.items():
        monkeypatch.setattr(settings, key, value)
    provider = SyntheticLeave()
    constructors: list[dict[str, object]] = []

    def construct(**kwargs: object) -> SyntheticLeave:
        constructors.append(kwargs)
        return provider

    monkeypatch.setattr(dependencies, "OpenAILeaveAssistantProvider", construct)
    assert client.post("/api/v1/demo/start").status_code == 200
    caps = client.get("/api/v1/demo/configuration").json()["aiCapabilities"]
    assert caps["approvalDraft"] and caps["leaveAssistant"] and not caps["policyEmbedding"]
    response = client.post("/api/v1/leave-agent/runs", json={"request": "다음 주 휴가"})
    assert response.status_code == 201, response.text
    assert response.json()["consultation"]["status"] == "NEEDS_INPUT"
    assert provider.calls == 1 and len(provider.safety_identifier) == 64
    assert constructors[0]["max_retries"] == 0 and constructors[0]["standard_tier"] is True
    denied = client.post("/api/v1/leave-assistant/consult", json={"request": "다음 주 휴가"})
    assert denied.status_code == 429 and provider.calls == 1
    with session_factory() as db:
        reservation = db.scalar(select(AIBudgetReservation))
        assert reservation is not None and reservation.status == "SETTLED"
        assert reservation.charged_micro_usd == 1650


def test_leave_flag_requires_budget() -> None:
    with pytest.raises(ValueError, match="explicit budget"):
        Settings(
            _env_file=None, public_demo_enabled=True, ai_enabled=False, public_leave_ai_enabled=True
        )


def test_leave_unknown_usage_freezes_shared_budget(
    budget_factory: sessionmaker[Session],
) -> None:
    from dataclasses import replace

    from app.ai.budgeted_leave_assistant import BudgetedLeaveAssistantProvider
    from app.ai.leave_assistant import LeaveAssistantProviderError
    from app.core.errors import ServiceUnavailableError
    from tests.test_budgeted_expense_draft import SyntheticProvider, provider_input, wrapped

    class BadUsage(SyntheticLeave):
        def structure(
            self, value: LeaveAssistantProviderInput, safety_identifier: str
        ) -> LeaveAssistantProviderResult:
            result = super().structure(value, safety_identifier)
            return replace(result, service_tier="priority")

    leave = BudgetedLeaveAssistantProvider(
        workspace_id="synthetic",
        factory=budget_factory,
        provider_factory=BadUsage,
        limits=rollout_limits(),
        check_authorization=lambda db: None,
    )
    payload = LeaveAssistantProviderInput(
        request="다음 주 휴가", answers=[], current_date=date(2026, 8, 31), timezone="Asia/Seoul"
    )
    with pytest.raises(LeaveAssistantProviderError, match="accounting"):
        leave.structure(payload, "actor")
    expense = SyntheticProvider()
    with pytest.raises(ServiceUnavailableError) as caught:
        wrapped(budget_factory, expense).prepare(provider_input(), "actor")
    assert caught.value.code == "AI_BUDGET_FROZEN" and expense.calls == 0

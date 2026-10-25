from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import (
    ApprovalDraftCandidate,
    ApprovalDraftProviderError,
    ApprovalDraftProviderInput,
    DraftIntent,
    DraftProviderResult,
    DraftProviderUsage,
)
from app.ai.budgeted_expense_draft import BudgetedExpenseDraftProvider
from app.ai.expense_pricing import MAX_REQUEST_MICRO_USD, MODEL, micro_usd
from app.core.ai_budget import AIBudgetLimits
from app.core.errors import AuthenticationError, ServiceUnavailableError
from app.models.ai_budget import AIBudgetCounter, AIBudgetReservation
from app.services import ai_budget
from tests.test_ai_budget import budget_factory as budget_factory


def rollout_limits(**updates: int) -> AIBudgetLimits:
    return AIBudgetLimits.model_validate(
        {
            "day_micro_usd": 500000,
            "month_micro_usd": 2000000,
            "day_admissions": 10,
            "scope_day_admissions": 5,
            "concurrent_requests": 1,
            **updates,
        }
    )


def provider_input() -> ApprovalDraftProviderInput:
    return ApprovalDraftProviderInput(
        request="CES 경비 17만원 정산",
        answers=[],
        current_date=date(2026, 8, 31),
        timezone="Asia/Seoul",
    )


def result() -> DraftProviderResult:
    return DraftProviderResult(
        candidate=ApprovalDraftCandidate(intent=DraftIntent.EXPENSE, amount=170000),
        provider="synthetic",
        model=MODEL,
        usage=DraftProviderUsage(1000, 200, 1200),
        latency_ms=1,
        service_tier="default",
    )


class SyntheticProvider:
    def __init__(self, output: DraftProviderResult | None = None) -> None:
        self.output = output or result()
        self.calls = 0
        self.should_fail = False

    def prepare(
        self, value: ApprovalDraftProviderInput, safety_identifier: str
    ) -> DraftProviderResult:
        self.calls += 1
        if self.should_fail:
            raise ApprovalDraftProviderError("synthetic timeout")
        return self.output


def wrapped(
    factory: sessionmaker[Session],
    provider: SyntheticProvider,
) -> BudgetedExpenseDraftProvider:
    return BudgetedExpenseDraftProvider(
        workspace_id="synthetic",
        factory=factory,
        provider_factory=lambda: provider,
        limits=rollout_limits(),
        check_authorization=lambda db: None,
    )


def test_price_rounding_and_entire_context_reservation() -> None:
    assert micro_usd(1, 0) == 1
    assert micro_usd(0, 1) == 5
    assert micro_usd(1000, 200) == 1650
    assert MAX_REQUEST_MICRO_USD == 307200
    for bad in (True, -1, 400001):
        with pytest.raises(ValueError):
            micro_usd(bad, 0)


def test_reservation_commits_before_authorization_and_provider_construction(
    budget_factory: sessionmaker[Session],
) -> None:
    events: list[str] = []
    provider = SyntheticProvider()

    def authorize(db: Session) -> None:
        gate = db.get(AIBudgetCounter, "global")
        day = db.get(AIBudgetCounter, "day:2026-08-31")
        assert gate is not None and gate.active_requests == 1
        assert day is not None and day.reserved_micro_usd == MAX_REQUEST_MICRO_USD
        events.append("authorization")

    def construct() -> SyntheticProvider:
        events.append("construct")
        return provider

    instance = BudgetedExpenseDraftProvider(
        workspace_id="synthetic",
        factory=budget_factory,
        provider_factory=construct,
        limits=rollout_limits(),
        check_authorization=authorize,
    )
    assert instance.prepare(provider_input(), "opaque").candidate.amount == 170000
    assert events == ["authorization", "construct"] and provider.calls == 1
    with budget_factory() as db:
        day = db.get(AIBudgetCounter, "day:2026-08-31")
        gate = db.get(AIBudgetCounter, "global")
        assert day is not None and gate is not None
        assert (day.spent_micro_usd, day.reserved_micro_usd, gate.active_requests) == (1650, 0, 0)


def test_provider_failure_consumes_full_reservation_without_retry(
    budget_factory: sessionmaker[Session],
) -> None:
    provider = SyntheticProvider()
    provider.should_fail = True
    with pytest.raises(ApprovalDraftProviderError):
        wrapped(budget_factory, provider).prepare(provider_input(), "opaque")
    assert provider.calls == 1
    with budget_factory() as db:
        rows = db.query(AIBudgetReservation).all()
        assert len(rows) == 1
        assert (rows[0].status, rows[0].charged_micro_usd) == ("UNCERTAIN", MAX_REQUEST_MICRO_USD)


@pytest.mark.parametrize("kind", ["model", "tier", "missing_usage", "over_output", "total"])
def test_unverifiable_usage_consumes_maximum_and_freezes_new_calls(
    budget_factory: sessionmaker[Session],
    kind: str,
) -> None:
    output = result()
    if kind == "model":
        output = replace(output, model="unpriced-model")
    elif kind == "tier":
        output = replace(output, service_tier="priority")
    elif kind == "missing_usage":
        output = replace(output, usage=replace(output.usage, known=False))
    elif kind == "over_output":
        output = replace(output, usage=DraftProviderUsage(1000, 1601, 2601))
    else:
        output = replace(output, usage=DraftProviderUsage(1000, 200, 0))
    provider = SyntheticProvider(output)
    with pytest.raises(ApprovalDraftProviderError):
        wrapped(budget_factory, provider).prepare(provider_input(), "opaque")
    with pytest.raises(ServiceUnavailableError) as caught:
        wrapped(budget_factory, provider).prepare(provider_input(), "opaque")
    assert caught.value.code == "AI_BUDGET_FROZEN" and provider.calls == 1


def test_expiry_after_admission_releases_cost_but_not_admission_and_never_calls_provider(
    budget_factory: sessionmaker[Session],
) -> None:
    provider = SyntheticProvider()

    def expired(db: Session) -> None:
        raise AuthenticationError("synthetic expired workspace")

    instance = BudgetedExpenseDraftProvider(
        workspace_id="synthetic",
        factory=budget_factory,
        provider_factory=lambda: provider,
        limits=rollout_limits(),
        check_authorization=expired,
    )
    with pytest.raises(AuthenticationError):
        instance.prepare(provider_input(), "opaque")
    assert provider.calls == 0
    with budget_factory() as db:
        day = db.get(AIBudgetCounter, "day:2026-08-31")
        assert day is not None
        assert (day.spent_micro_usd, day.reserved_micro_usd, day.admissions) == (0, 0, 1)


def test_budget_denial_never_calls_provider_and_oversized_input_never_reserves(
    budget_factory: sessionmaker[Session],
) -> None:
    provider = SyntheticProvider()
    instance = BudgetedExpenseDraftProvider(
        workspace_id="synthetic",
        factory=budget_factory,
        provider_factory=lambda: provider,
        limits=rollout_limits(scope_day_admissions=1),
        check_authorization=lambda db: None,
    )
    with pytest.raises(ApprovalDraftProviderError):
        instance.prepare(provider_input().model_copy(update={"answers": ["x" * 2001]}), "opaque")
    instance.prepare(provider_input(), "opaque")
    with pytest.raises(ai_budget.AIBudgetLimitError):
        instance.prepare(provider_input(), "opaque")
    assert provider.calls == 1

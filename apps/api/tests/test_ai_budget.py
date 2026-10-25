from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.errors import ConflictError, ServiceUnavailableError
from app.models.ai_budget import AIBudgetCounter, AIBudgetReservation
from app.services import ai_budget


@pytest.fixture
def budget_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[sessionmaker[Session]]:
    engine = create_engine("sqlite:///" + str(tmp_path / "budget.db"))
    Base.metadata.create_all(
        engine,
        tables=[
            Base.metadata.tables["ai_budget_counters"],
            Base.metadata.tables["ai_budget_reservations"],
        ],
    )
    monkeypatch.setattr(ai_budget, "database_seconds", lambda db: epoch("2026-08-31T23:59:00"))
    yield sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    engine.dispose()


def epoch(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("Asia/Seoul")).timestamp())


def limits(**updates: int) -> ai_budget.AIBudgetLimits:
    return ai_budget.AIBudgetLimits.model_validate(
        {
            "day_micro_usd": 500,
            "month_micro_usd": 1000,
            "day_admissions": 10,
            "scope_day_admissions": 3,
            "concurrent_requests": 4,
            **updates,
        }
    )


def reserve(
    factory: sessionmaker[Session],
    workspace: str = "synthetic-workspace",
    cost: int = 200,
    policy: ai_budget.AIBudgetLimits | None = None,
) -> ai_budget.BudgetReceipt:
    with factory() as db:
        return ai_budget.reserve(
            db, workspace_id=workspace, maximum_micro_usd=cost, limits=policy or limits()
        )


def test_reserve_is_committed_and_settlement_is_idempotent(
    budget_factory: sessionmaker[Session],
) -> None:
    receipt = reserve(budget_factory)
    with budget_factory() as db:
        counter = db.get(AIBudgetCounter, "day:2026-08-31")
        assert counter is not None and counter.reserved_micro_usd == 200
    with budget_factory() as db:
        settled = ai_budget.settle(db, receipt.id, actual_micro_usd=80)
    with budget_factory() as db:
        assert ai_budget.settle(db, receipt.id, actual_micro_usd=80) == settled
    with budget_factory() as db:
        day = db.get(AIBudgetCounter, "day:2026-08-31")
        gate = db.get(AIBudgetCounter, "global")
        assert day is not None and gate is not None
        assert (day.spent_micro_usd, day.reserved_micro_usd, day.admissions) == (80, 0, 1)
        assert gate.active_requests == 0
    with budget_factory() as db, pytest.raises(ConflictError):
        ai_budget.settle(db, receipt.id, actual_micro_usd=0)


def test_unknown_billing_consumes_maximum_and_admission_is_not_refunded(
    budget_factory: sessionmaker[Session],
) -> None:
    receipt = reserve(budget_factory, policy=limits(scope_day_admissions=1))
    with budget_factory() as db:
        assert ai_budget.settle(db, receipt.id, actual_micro_usd=None).status == "UNCERTAIN"
    with budget_factory() as db:
        row = db.get(AIBudgetCounter, "day:2026-08-31")
        assert row is not None and row.spent_micro_usd == 200 and row.reserved_micro_usd == 0
    # Same workspace includes both author and approver identities; usage cannot be bypassed by role.
    with pytest.raises(ai_budget.AIBudgetLimitError):
        reserve(budget_factory, policy=limits(scope_day_admissions=1))
    reserve(budget_factory, workspace="another-workspace", cost=100)


def test_cost_reservations_bound_unsettled_requests_and_rejection_rolls_back(
    budget_factory: sessionmaker[Session],
) -> None:
    receipt = reserve(budget_factory, cost=400)
    with pytest.raises(ai_budget.AIBudgetLimitError):
        reserve(budget_factory, workspace="rejected-workspace", cost=101)
    with budget_factory() as db:
        assert db.scalar(select(func.count()).select_from(AIBudgetCounter)) == 4
        assert db.scalar(select(func.count()).select_from(AIBudgetReservation)) == 1
    with budget_factory() as db:
        ai_budget.settle(db, receipt.id, actual_micro_usd=100)
    reserve(budget_factory, workspace="another-workspace", cost=400)


def test_global_concurrency_survives_midnight_and_crash_does_not_expire_slot(
    budget_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = reserve(budget_factory, policy=limits(concurrent_requests=1))
    monkeypatch.setattr(ai_budget, "database_seconds", lambda db: epoch("2026-09-01T00:01:00"))
    with pytest.raises(ai_budget.AIBudgetLimitError):
        reserve(budget_factory, policy=limits(concurrent_requests=1))
    with budget_factory() as db:
        ai_budget.settle(db, receipt.id, actual_micro_usd=100)
    reserve(budget_factory, policy=limits(concurrent_requests=1))
    with budget_factory() as db:
        old = db.get(AIBudgetCounter, "month:2026-08")
        new = db.get(AIBudgetCounter, "month:2026-09")
        assert old is not None and new is not None
        assert old.spent_micro_usd == 100 and old.reserved_micro_usd == 0
        assert new.spent_micro_usd == 0 and new.reserved_micro_usd == 200


def test_month_cost_does_not_reset_on_new_day(
    budget_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = limits(month_micro_usd=250)
    monkeypatch.setattr(ai_budget, "database_seconds", lambda db: epoch("2026-08-30T10:00:00"))
    receipt = reserve(budget_factory, policy=policy)
    with budget_factory() as db:
        ai_budget.settle(db, receipt.id, actual_micro_usd=200)
    monkeypatch.setattr(ai_budget, "database_seconds", lambda db: epoch("2026-08-31T10:00:00"))
    with pytest.raises(ai_budget.AIBudgetLimitError):
        reserve(budget_factory, cost=51, policy=policy)


def test_overrun_records_real_charge_and_freezes_all_future_windows(
    budget_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = reserve(budget_factory)
    with budget_factory() as db:
        assert ai_budget.settle(db, receipt.id, actual_micro_usd=700).status == "OVERRUN"
    with budget_factory() as db:
        counter = db.get(AIBudgetCounter, "day:2026-08-31")
        assert counter is not None and counter.spent_micro_usd == 700
    monkeypatch.setattr(ai_budget, "database_seconds", lambda db: epoch("2026-09-01T10:00:00"))
    with pytest.raises(ServiceUnavailableError) as caught:
        reserve(budget_factory, workspace="new-workspace", policy=limits(month_micro_usd=10000))
    assert caught.value.code == "AI_BUDGET_FROZEN"


def test_daily_admission_limit_counts_zero_cost_settlements(
    budget_factory: sessionmaker[Session],
) -> None:
    policy = limits(day_admissions=1)
    receipt = reserve(budget_factory, policy=policy)
    with budget_factory() as db:
        ai_budget.settle(db, receipt.id, actual_micro_usd=0)
    with pytest.raises(ai_budget.AIBudgetLimitError):
        reserve(budget_factory, workspace="new-workspace", policy=policy)


def test_fresh_session_requirement_preserves_caller_transaction(
    budget_factory: sessionmaker[Session],
) -> None:
    with budget_factory() as db:
        db.execute(text("SELECT 1"))
        with pytest.raises(ValueError, match="separate fresh session"):
            ai_budget.reserve(db, workspace_id="synthetic", maximum_micro_usd=100, limits=limits())
        assert db.in_transaction()
        db.rollback()


def test_database_failure_is_closed_without_leaking_diagnostics(
    budget_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(db: Session) -> int:
        raise OperationalError("synthetic", {}, Exception("private diagnostic"))

    monkeypatch.setattr(ai_budget, "database_seconds", fail)
    with pytest.raises(ServiceUnavailableError) as caught:
        reserve(budget_factory)
    assert caught.value.code == "AI_BUDGET_UNAVAILABLE"
    assert "private diagnostic" not in str(caught.value)


@pytest.mark.parametrize("value", [-1, 0, True])
def test_invalid_budget_or_cost_never_creates_reservation(
    budget_factory: sessionmaker[Session],
    value: int,
) -> None:
    with pytest.raises((ValueError, ValidationError)):
        limits(day_micro_usd=value)
    with pytest.raises(ValueError):
        reserve(budget_factory, cost=value)


def test_sqlite_separate_writers_cannot_over_admit(budget_factory: sessionmaker[Session]) -> None:
    barrier = Barrier(8)

    def attempt(index: int) -> bool:
        barrier.wait(timeout=10)
        try:
            reserve(budget_factory, workspace=f"synthetic-{index}")
            return True
        except ai_budget.AIBudgetLimitError:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(attempt, range(8))) == 2


def test_clock_reversal_rejects_new_period_without_changing_reservation(
    budget_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = reserve(budget_factory)
    monkeypatch.setattr(ai_budget, "database_seconds", lambda db: epoch("2026-08-30T23:59:00"))
    with pytest.raises(ServiceUnavailableError) as caught:
        reserve(budget_factory, workspace="another-workspace")
    assert caught.value.code == "AI_BUDGET_CLOCK_REVERSED"
    with budget_factory() as db:
        assert db.scalar(select(func.count()).select_from(AIBudgetCounter)) == 4
        assert db.scalar(select(func.count()).select_from(AIBudgetReservation)) == 1
    # Existing reservations can still be settled without opening another time window.
    with budget_factory() as db:
        ai_budget.settle(db, receipt.id, actual_micro_usd=None)

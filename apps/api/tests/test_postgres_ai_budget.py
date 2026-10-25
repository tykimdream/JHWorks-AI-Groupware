"""Shared budget races in the existing dedicated loopback PostgreSQL fixture only."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.models.ai_budget import AIBudgetCounter
from app.services import ai_budget
from tests.test_ai_budget import epoch, limits, reserve
from tests.test_postgres_approval_lists import session_factory as session_factory


@pytest.mark.parametrize("kind", ["cost", "concurrency", "scope"])
def test_postgres_separate_connections_cannot_over_admit(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    monkeypatch.setattr(ai_budget, "database_seconds", lambda db: epoch("2026-08-31T10:00:00"))
    policy = limits(
        day_micro_usd=500 if kind == "cost" else 10000,
        month_micro_usd=10000,
        concurrent_requests=2 if kind == "concurrency" else 8,
        scope_day_admissions=2 if kind == "scope" else 8,
    )
    barrier = Barrier(8)

    def attempt(index: int) -> bool:
        barrier.wait(timeout=20)
        try:
            reserve(
                session_factory,
                workspace="shared" if kind == "scope" else f"scope-{index}",
                policy=policy,
            )
            return True
        except ai_budget.AIBudgetLimitError:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(attempt, range(8))) == 2
    with session_factory() as db:
        gate = db.get(AIBudgetCounter, "global")
        day = db.get(AIBudgetCounter, "day:2026-08-31")
        assert gate is not None and day is not None
        assert gate.active_requests == 2
        assert day.reserved_micro_usd == 400 and day.admissions == 2


def test_postgres_duplicate_settlement_charges_and_releases_once(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_budget, "database_seconds", lambda db: epoch("2026-08-31T10:00:00"))
    receipt = reserve(session_factory)
    barrier = Barrier(4)

    def finish(_: int) -> str:
        barrier.wait(timeout=20)
        with session_factory() as db:
            return ai_budget.settle(db, receipt.id, actual_micro_usd=80).status

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(finish, range(4))) == ["SETTLED"] * 4
    with session_factory() as db:
        day = db.get(AIBudgetCounter, "day:2026-08-31")
        gate = db.get(AIBudgetCounter, "global")
        assert day is not None and gate is not None
        assert (day.spent_micro_usd, day.reserved_micro_usd, gate.active_requests) == (80, 0, 0)

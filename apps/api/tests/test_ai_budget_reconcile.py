import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.models.ai_budget import AIBudgetCounter
from app.ops.ai_budget_reconcile import reconcile
from app.services import ai_budget
from tests.test_ai_budget import budget_factory as budget_factory
from tests.test_ai_budget import epoch, reserve


def test_reconcile_is_read_only_by_default_and_rejects_unreviewed_apply(
    budget_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = reserve(budget_factory)
    monkeypatch.setattr(
        "app.ops.ai_budget_reconcile.database_seconds", lambda db: epoch("2026-09-01T00:20:00")
    )
    assert reconcile(budget_factory, [receipt.id])[0]["eligible"] is True
    for kwargs in ({}, {"public_ai_enabled": True, "confirmed_no_live_calls": True}):
        with pytest.raises(ValueError):
            reconcile(budget_factory, [receipt.id], apply=True, **kwargs)
    with pytest.raises(ValueError):
        reconcile(budget_factory, [], apply=True, confirmed_no_live_calls=True)
    with budget_factory() as db:
        gate = db.get(AIBudgetCounter, "global")
        assert gate is not None and gate.active_requests == 1
    for _ in range(2):
        report = reconcile(budget_factory, [receipt.id], apply=True, confirmed_no_live_calls=True)
        assert report[0]["chargedMicroUsd"] == 200 and report[0]["status"] == "UNCERTAIN"
    with budget_factory() as db:
        gate = db.get(AIBudgetCounter, "global")
        day = db.get(AIBudgetCounter, "day:2026-08-31")
        assert gate is not None and day is not None
        assert gate.active_requests == 0 and day.spent_micro_usd == 200


def test_reconcile_refuses_young_unknown_or_duplicate_targets(
    budget_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = reserve(budget_factory)
    monkeypatch.setattr(
        "app.ops.ai_budget_reconcile.database_seconds", lambda db: epoch("2026-09-01T00:01:00")
    )
    for ids in ([receipt.id], [receipt.id, "missing"], [receipt.id, receipt.id]):
        with pytest.raises(ValueError):
            reconcile(budget_factory, ids, apply=True, confirmed_no_live_calls=True)
    with budget_factory() as db:
        gate = db.get(AIBudgetCounter, "global")
        assert gate is not None and gate.active_requests == 1
    # Accounting disagreement/overrun freezes are not cleared by reconciliation.
    with budget_factory() as db:
        ai_budget.settle(db, receipt.id, actual_micro_usd=None, freeze=True)
    monkeypatch.setattr(
        "app.ops.ai_budget_reconcile.database_seconds", lambda db: epoch("2026-09-01T00:20:00")
    )
    reconcile(budget_factory, [receipt.id], apply=True, confirmed_no_live_calls=True)
    with budget_factory() as db:
        gate = db.get(AIBudgetCounter, "global")
        assert gate is not None and gate.is_frozen

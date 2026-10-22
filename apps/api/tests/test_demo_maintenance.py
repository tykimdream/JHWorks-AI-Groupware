import json
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.demo_feedback import DemoFeedback
from app.models.demo_workspace import DemoWorkspace
from app.models.employee import Employee
from app.ops import demo_maintenance as maintenance
from tests.test_demo_visitor import _expire, _start
from tests.test_demo_visitor import public_demo as public_demo
from tests.test_feedback_retention import add_feedback


def test_maintenance_default_preserves_then_apply_retries_safely(
    client: TestClient,
    public_demo: None,
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        before = db.scalar(select(func.count()).select_from(Employee))
    visit = _start(client)
    _expire(session_factory, visit["employee"]["id"])
    with session_factory() as db:
        add_feedback(db, "expired_synthetic", 1)
        db.commit()
    plan = maintenance.run_maintenance(session_factory)
    assert plan["status"] == "passed" and plan["dryRun"] is True
    assert plan["steps"]["feedback"] == {"expired": 1, "removed": 0, "stored": 1}
    assert plan["steps"]["workspaces"] == {"planned": 1, "removed": 0}
    result = maintenance.run_maintenance(session_factory, apply=True)
    assert result["status"] == "passed"
    assert result["steps"]["feedback"]["removed"] == 1
    assert result["steps"]["workspaces"]["removed"] == 1
    again = maintenance.run_maintenance(session_factory, apply=True)
    assert again["steps"]["feedback"]["removed"] == 0
    assert again["steps"]["workspaces"]["removed"] == 0
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Employee)) == before


def test_workspace_failure_preserves_completed_feedback_step_and_hides_error(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with session_factory() as db:
        add_feedback(db, "expired_synthetic", 1)
        db.commit()

    def fail(*args: Any, **kwargs: Any) -> None:
        raise ValueError("Synthetic private content must never enter logs")

    monkeypatch.setattr(maintenance, "cleanup_expired_demo", fail)
    result = maintenance.run_maintenance(session_factory, apply=True)
    assert result["status"] == "failed" and result["severity"] == "ERROR"
    assert result["stage"] == "workspaces" and result["errorType"] == "ValueError"
    assert result["steps"] == {"feedback": {"expired": 1, "removed": 1, "stored": 0}}
    assert "private content" not in json.dumps(result)
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DemoFeedback)) == 0


def test_feedback_failure_stops_before_workspace_changes(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Synthetic database failure")

    def unexpected(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Workspace cleanup must not run after failed feedback retention")

    monkeypatch.setattr(maintenance, "purge_expired_feedback", fail)
    monkeypatch.setattr(maintenance, "cleanup_expired_demo", unexpected)
    result = maintenance.run_maintenance(session_factory, apply=True)
    assert result["stage"] == "feedback" and result["steps"] == {}


def test_cli_requires_opt_in_and_reports_failure_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["maintenance"])
    with pytest.raises(SystemExit) as exc:
        maintenance.main()
    assert exc.value.code == 2
    capsys.readouterr()
    monkeypatch.setattr(get_settings(), "public_demo_enabled", True)
    monkeypatch.setattr(get_settings(), "ai_enabled", False)

    def fail_factory() -> Session:
        raise RuntimeError("Synthetic connection string")

    monkeypatch.setattr(maintenance, "SessionLocal", fail_factory)
    with pytest.raises(SystemExit) as exc:
        maintenance.main()
    assert exc.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "failed" and "connection string" not in json.dumps(result)


def test_cleanup_is_bounded_and_does_not_reset_admission(
    client: TestClient,
    public_demo: None,
    session_factory: sessionmaker[Session],
) -> None:
    from app.models.demo_start_budget import DemoStartBudget

    for _ in range(2):
        client.cookies.clear()
        visit = _start(client)
        _expire(session_factory, visit["employee"]["id"])
    result = maintenance.run_maintenance(session_factory, apply=True, batch_size=1)
    assert result["steps"]["workspaces"]["removed"] == 1
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DemoWorkspace)) == 1
        assert db.scalar(select(DemoStartBudget.starts_used)) == 2


def test_cli_success_is_dry_by_default(
    public_demo: None,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(maintenance, "SessionLocal", session_factory)
    monkeypatch.setattr(sys, "argv", ["maintenance"])
    with pytest.raises(SystemExit) as exc:
        maintenance.main()
    assert exc.value.code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "passed" and report["dryRun"] is True
    assert report["steps"]["feedback"]["removed"] == 0
    assert report["steps"]["workspaces"]["removed"] == 0

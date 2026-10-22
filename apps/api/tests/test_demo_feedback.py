from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.demo_feedback import DemoFeedback
from app.models.demo_workspace import DemoWorkspace
from app.services import demo_feedback
from app.services.login_budget import database_seconds
from tests.test_demo_visitor import _start
from tests.test_demo_visitor import public_demo as public_demo


def payload() -> dict[str, Any]:
    return {
        "category": "usability",
        "screen": "approvals",
        "message": "Synthetic feedback: the approval action was hard to find.",
        "consent": True,
    }


def test_feedback_is_private_bounded_and_idempotent_after_business_budget_exhaustion(
    client: TestClient,
    public_demo: None,
    session_factory: sessionmaker[Session],
) -> None:
    _start(client)
    with session_factory() as db:
        row = db.scalar(select(DemoWorkspace))
        assert row is not None
        row.writes_used = row.write_limit
        row.requests_used = row.request_limit
        db.commit()
    first = client.post("/api/v1/demo/feedback", json=payload())
    assert first.status_code == 200
    assert set(first.json()) == {"id", "status"}
    again = client.post("/api/v1/demo/feedback", json=payload())
    assert again.json() == first.json()
    assert (
        client.post(
            "/api/v1/demo/feedback", json={**payload(), "message": "A different synthetic message"}
        ).status_code
        == 409
    )
    assert client.get("/api/v1/demo/feedback").status_code == 405
    assert client.get("/api/v1/demo/feedback/" + first.json()["id"]).status_code == 404
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DemoFeedback)) == 1
        stored = db.scalar(select(DemoFeedback))
        assert stored is not None and len(stored.workspace_hash) == 64
        assert stored.workspace_hash != row.id


@pytest.mark.parametrize(
    "change",
    [
        {"consent": False},
        {"message": "short"},
        {"message": " " * 100},
        {"message": "x" * 1001},
        {"employeeId": "emp_sales_001"},
        {"message": "Contact synthetic.person@example.test please"},
        {"message": "Synthetic Bearer example-private-token"},
    ],
)
def test_feedback_validation(client: TestClient, public_demo: None, change: dict[str, Any]) -> None:
    _start(client)
    assert client.post("/api/v1/demo/feedback", json={**payload(), **change}).status_code == 422


def test_feedback_capacity_and_expiry_fail_closed(
    client: TestClient,
    public_demo: None,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(demo_feedback, "MAX_FEEDBACK", 1)
    _start(client)
    assert client.post("/api/v1/demo/feedback", json=payload()).status_code == 200
    client.cookies.clear()
    _start(client)
    result = client.post("/api/v1/demo/feedback", json=payload())
    assert result.status_code == 429
    assert "no-store" in result.headers["cache-control"]
    with session_factory() as db:
        rows = list(db.scalars(select(DemoWorkspace)))
        for row in rows:
            row.expires_at_epoch = database_seconds(db) - 1
        db.commit()
    assert client.post("/api/v1/demo/feedback", json=payload()).status_code == 401


def test_unauthenticated_and_private_accounts_cannot_submit(client: TestClient) -> None:
    assert client.post("/api/v1/demo/feedback", json=payload()).status_code == 401
    from app.core.config import get_settings
    from app.core.security import create_session_token

    client.cookies.set(get_settings().session_cookie_name, create_session_token("emp_sales_001"))
    assert client.post("/api/v1/demo/feedback", json=payload()).status_code == 401


def test_operator_summary_hides_text_and_retention_purge_is_explicit(
    client: TestClient,
    public_demo: None,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import json
    import sys

    from app.ops import demo_feedback as operator

    _start(client)
    assert client.post("/api/v1/demo/feedback", json=payload()).status_code == 200
    with session_factory() as db:
        row = db.scalar(select(DemoFeedback))
        assert row is not None
        row.created_at_epoch = database_seconds(db) - demo_feedback.RETENTION_SECONDS - 1
        db.commit()
    monkeypatch.setattr(operator, "SessionLocal", session_factory)
    monkeypatch.setattr(sys, "argv", ["feedback", "--purge-expired"])
    operator.main()
    report = json.loads(capsys.readouterr().out)
    assert report["expired"] == 1 and report["stored"] == 1 and report["removed"] == 0
    assert "message" not in report and "submissions" not in report
    monkeypatch.setattr(sys, "argv", ["feedback", "--purge-expired", "--apply"])
    operator.main()
    report = json.loads(capsys.readouterr().out)
    assert report["stored"] == 0 and report["removed"] == 1
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DemoWorkspace)) == 1

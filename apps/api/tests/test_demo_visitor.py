from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.errors import ConflictError
from app.core.security import create_session_token
from app.models.approval import Approval, ApprovalLine
from app.models.demo_start_budget import DemoStartBudget
from app.models.demo_workspace import DemoWorkspace
from app.models.employee import Employee
from app.models.enums import ApprovalLineStatus
from app.services.demo_cleanup import cleanup_expired_demo
from app.services.login_budget import database_seconds


@pytest.fixture
def public_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    # Keep the cached object shared with middleware and existing test fixtures.
    settings = get_settings()
    monkeypatch.setattr(settings, "public_demo_enabled", True)
    monkeypatch.setattr(settings, "ai_enabled", False)


def _start(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/v1/demo/start")
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["cache-control"]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    return dict(response.json())


def _count(factory: sessionmaker[Session], model: Any) -> int:
    with factory() as db:
        return db.scalar(select(func.count()).select_from(model)) or 0


def test_demo_is_opt_in(client: TestClient) -> None:
    assert client.get("/api/v1/demo/configuration").json()["enabled"] is False
    assert client.post("/api/v1/demo/start").status_code == 404


def test_public_demo_requires_ai_off() -> None:
    with pytest.raises(ValidationError, match="AI_ENABLED=false"):
        Settings(_env_file=None, public_demo_enabled=True, ai_enabled=True)


def test_public_mode_rejects_private_sessions_and_password_login(
    client: TestClient,
    public_demo: None,
) -> None:
    client.cookies.set(get_settings().session_cookie_name, create_session_token("emp_sales_001"))
    assert client.get("/api/v1/employees/me").status_code == 401
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "seojin.yoon@jhworks.test",
            "password": "demo1234",
        },
    )
    assert response.status_code == 401 and "set-cookie" not in response.headers


def test_start_is_isolated_reused_and_role_switch_stays_in_workspace(
    client: TestClient,
    public_demo: None,
    session_factory: sessionmaker[Session],
) -> None:
    first = _start(client)
    again = _start(client)
    assert first["employee"]["id"] == again["employee"]["id"]
    with session_factory() as db:
        assert db.scalar(select(DemoStartBudget.starts_used)) == 1
        assert db.scalar(select(func.count()).select_from(DemoWorkspace)) == 1
        assert database_seconds(db) < first["expiresAtEpoch"] <= database_seconds(db) + 900
    switched = client.post("/api/v1/demo/role", json={"role": "manager"})
    assert switched.status_code == 200
    assert switched.json()["employee"]["id"] == first["employee"]["manager"]["id"]
    assert switched.json()["expiresAtEpoch"] == first["expiresAtEpoch"]
    injected = client.post(
        "/api/v1/demo/role",
        json={
            "role": "author",
            "employeeId": "emp_sales_001",
        },
    )
    assert injected.status_code == 422
    back = client.post("/api/v1/demo/role", json={"role": "author"})
    assert back.status_code == 200 and back.json()["employee"]["id"] == first["employee"]["id"]
    client.cookies.clear()
    other = _start(client)
    assert other["employee"]["departmentId"] != first["employee"]["departmentId"]


def test_daily_and_retained_caps_include_expired_spaces(
    client: TestClient,
    public_demo: None,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "demo_starts_per_day", 2)
    monkeypatch.setattr(get_settings(), "demo_retained_workspaces", 1)
    first = _start(client)
    client.cookies.clear()
    with session_factory() as db:
        workspace = db.scalar(select(DemoWorkspace))
        assert workspace is not None
        workspace.expires_at_epoch = database_seconds(db) - 1
        db.commit()
    assert client.post("/api/v1/demo/start").status_code == 429
    assert client.post("/api/v1/demo/start").status_code == 429
    assert _count(session_factory, DemoWorkspace) == 1
    with session_factory() as db:
        assert db.get(Employee, first["employee"]["id"]) is not None
        assert db.scalar(select(DemoStartBudget.starts_used)) == 2


def test_request_cap_blocks_reads_but_logout_is_available(
    client: TestClient,
    public_demo: None,
    session_factory: sessionmaker[Session],
) -> None:
    first = _start(client)
    with session_factory() as db:
        actor = db.get(Employee, first["employee"]["id"])
        assert actor is not None
        workspace = db.get(DemoWorkspace, actor.demo_workspace_id)
        assert workspace is not None
        workspace.request_limit = 1
        db.commit()
    assert client.get("/api/v1/employees/me").status_code == 200
    denied = client.get("/api/v1/employees/me")
    assert denied.status_code == 429
    assert denied.json()["error"]["code"] == "DEMO_REQUEST_LIMIT_REACHED"
    assert client.post("/api/v1/auth/logout").status_code == 200


def _expire(factory: sessionmaker[Session], employee_id: str) -> None:
    with factory() as db:
        actor = db.get(Employee, employee_id)
        assert actor is not None
        workspace = db.get(DemoWorkspace, actor.demo_workspace_id)
        assert workspace is not None
        workspace.expires_at_epoch = database_seconds(db) - 86401
        db.commit()


def test_cleanup_dry_run_and_apply_preserve_private_and_active_data(
    client: TestClient,
    public_demo: None,
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        private = [
            (row.id, row.email, row.department_id, row.manager_id)
            for row in db.scalars(select(Employee))
        ]
    first = _start(client)
    created = client.post(
        "/api/v1/approvals",
        json={
            "type": "GENERAL",
            "title": "Synthetic expiry cleanup",
            "content": "Synthetic content",
            "details": {"kind": "GENERAL"},
        },
    )
    assert created.status_code == 201
    approval = created.json()
    assert (
        client.post(
            "/api/v1/approvals/" + approval["id"] + "/submit", json={"version": approval["version"]}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/leave-agent/runs", json={"request": "Synthetic consultation"}
        ).status_code
        == 201
    )
    client.cookies.clear()
    active = _start(client)
    _expire(session_factory, first["employee"]["id"])
    with session_factory() as db:
        result = cleanup_expired_demo(db)
        assert result.planned == 1 and result.removed == 0
    assert _count(session_factory, DemoWorkspace) == 2
    with session_factory() as db:
        result = cleanup_expired_demo(db, apply=True)
        assert result.removed == 1
    with session_factory() as db:
        assert db.get(Employee, first["employee"]["id"]) is None
        assert db.get(Employee, active["employee"]["id"]) is not None
        assert db.get(Approval, approval["id"]) is None
        assert [
            (row.id, row.email, row.department_id, row.manager_id)
            for row in db.scalars(select(Employee).where(Employee.demo_workspace_id.is_(None)))
        ] == private
        assert db.scalar(select(DemoStartBudget.starts_used)) == 2


def test_cleanup_refuses_cross_reference_without_partial_deletion(
    client: TestClient,
    public_demo: None,
    session_factory: sessionmaker[Session],
) -> None:
    first = _start(client)
    created = client.post(
        "/api/v1/approvals",
        json={
            "type": "GENERAL",
            "title": "Synthetic malformed relationship",
            "content": "Synthetic content",
            "details": {"kind": "GENERAL"},
        },
    ).json()
    with session_factory() as db:
        db.add(
            ApprovalLine(
                id="synthetic_cross_line",
                approval_id=created["id"],
                approver_id="emp_sales_001",
                step=1,
                round=1,
                status=ApprovalLineStatus.PENDING,
            )
        )
        db.commit()
    _expire(session_factory, first["employee"]["id"])
    with session_factory() as db, pytest.raises(ConflictError, match="unexpected relationship"):
        cleanup_expired_demo(db, apply=True)
    with session_factory() as db:
        assert db.get(Employee, first["employee"]["id"]) is not None
        assert db.get(Employee, "emp_sales_001") is not None
        assert db.get(Approval, created["id"]) is not None


def test_failed_provision_rolls_back_partial_graph_without_leaking_error(
    client: TestClient,
    public_demo: None,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import OperationalError

    before = _count(session_factory, Employee)
    original = Session.flush

    def fail_manager_flush(db: Session, *args: Any, **kwargs: Any) -> None:
        if any(isinstance(row, Employee) and row.id.startswith("demo_mgr_") for row in db.new):
            raise OperationalError("synthetic", {}, Exception("synthetic sensitive database value"))
        original(db, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", fail_manager_flush)
    result = client.post("/api/v1/demo/start")
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "DEMO_START_UNAVAILABLE"
    assert "sensitive database value" not in result.text
    assert "set-cookie" not in result.headers
    assert _count(session_factory, DemoWorkspace) == 0
    assert _count(session_factory, DemoStartBudget) == 0
    assert _count(session_factory, Employee) == before


def test_daily_window_recovers_without_accepting_clock_rollback(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import demo_visitor

    settings = Settings(_env_file=None, demo_starts_per_day=1)
    seconds = [1700000000]
    monkeypatch.setattr(demo_visitor, "database_seconds", lambda db: seconds[0])
    with session_factory() as db:
        demo_visitor.start_visit_safely(db, settings, None)
    with session_factory() as db, pytest.raises(demo_visitor.DemoStartLimitError):
        demo_visitor.start_visit_safely(db, settings, None)
    seconds[0] += 86400
    with session_factory() as db:
        demo_visitor.start_visit_safely(db, settings, None)
    seconds[0] -= 86400
    with session_factory() as db, pytest.raises(demo_visitor.DemoStartLimitError):
        demo_visitor.start_visit_safely(db, settings, None)
    assert _count(session_factory, DemoWorkspace) == 2

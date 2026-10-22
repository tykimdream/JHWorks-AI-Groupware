from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.security import create_session_token
from app.models.demo_workspace import DemoWorkspace
from app.models.employee import Department, Employee
from app.services import demo_workspace
from app.services.login_budget import database_seconds
from tests.conftest import FakeWorkAssistantProvider


def setup_workspaces(factory: sessionmaker[Session], limit: int = 20) -> None:
    with factory() as db:
        expiry = database_seconds(db) + 3600
        for name, department_id, ids in [
            ("demo_a", "dept_sales", ["emp_sales_001", "emp_sales_002", "emp_sales_mgr_001"]),
            ("demo_b", "dept_engineering", ["emp_eng_001", "emp_eng_mgr_001"]),
        ]:
            department = db.get(Department, department_id)
            assert department is not None
            department.parent_department_id = None
            db.add(
                DemoWorkspace(
                    id=name,
                    department_id=department_id,
                    expires_at_epoch=expiry,
                    write_limit=limit,
                    writes_used=0,
                    is_active=True,
                )
            )
            db.flush()
            for employee_id in ids:
                employee = db.get(Employee, employee_id)
                assert employee is not None
                employee.demo_workspace_id = name
                if employee.id.endswith("mgr_001"):
                    employee.manager_id = None
        db.commit()


def set_actor(client: TestClient, employee_id: str) -> None:
    client.cookies.clear()
    client.cookies.set(
        get_settings().session_cookie_name,
        create_session_token(employee_id),
        domain="testserver.local",
        path="/",
    )


def draft_body() -> dict[str, Any]:
    return {
        "type": "GENERAL",
        "title": "Synthetic visitor approval",
        "content": "Independent synthetic content",
        "details": {"kind": "GENERAL"},
    }


def usage(factory: sessionmaker[Session], name: str = "demo_a") -> int:
    with factory() as db:
        row = db.get(DemoWorkspace, name)
        assert row is not None
        return row.writes_used


def test_demo_organization_is_scoped_by_server_identity(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    setup_workspaces(session_factory)
    set_actor(client, "emp_sales_001")
    result = client.get("/api/v1/departments", headers={"X-Workspace-ID": "demo_b"})
    assert result.status_code == 200
    assert [item["id"] for item in result.json()] == ["dept_sales"]
    assert usage(session_factory) == 0
    set_actor(client, "emp_eng_001")
    assert [item["id"] for item in client.get("/api/v1/departments").json()] == ["dept_engineering"]


@pytest.mark.parametrize(
    "broken", ["expired", "inactive", "department", "parent", "manager", "department_manager"]
)
def test_expiry_and_broken_membership_fail_closed(
    client: TestClient,
    session_factory: sessionmaker[Session],
    broken: str,
) -> None:
    setup_workspaces(session_factory)
    with session_factory() as db:
        actor = db.get(Employee, "emp_sales_001")
        workspace = db.get(DemoWorkspace, "demo_a")
        department = db.get(Department, "dept_sales")
        assert actor is not None and workspace is not None and department is not None
        if broken == "expired":
            workspace.expires_at_epoch = database_seconds(db) - 1
        elif broken == "inactive":
            workspace.is_active = False
        elif broken == "department":
            actor.department_id = "dept_engineering"
        elif broken == "parent":
            department.parent_department_id = "dept_executive"
        elif broken == "manager":
            actor.manager_id = "emp_eng_mgr_001"
        else:
            department.manager_employee_id = "emp_eng_mgr_001"
        db.commit()
    set_actor(client, "emp_sales_001")
    for method, path, body in [
        ("GET", "/api/v1/employees/me", None),
        ("POST", "/api/v1/approvals", draft_body()),
    ]:
        response = client.request(method, path, json=body)
        assert response.status_code == 401
        assert "no-store" in response.headers["cache-control"]
    assert usage(session_factory) == 0
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "seojin.yoon@jhworks.test",
            "password": "demo1234",
        },
    )
    assert login.status_code == 401
    assert "set-cookie" not in login.headers


def test_lifetime_budget_is_shared_durable_and_does_not_block_reads_or_logout(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    setup_workspaces(session_factory, limit=2)
    set_actor(client, "emp_sales_001")
    # A forbidden business operation still consumes an admission.
    rejected = client.post("/api/v1/approvals/missing/submit", json={"version": 1})
    assert rejected.status_code == 404
    assert usage(session_factory) == 1
    set_actor(client, "emp_sales_mgr_001")
    created = client.post("/api/v1/approvals", json=draft_body())
    assert created.status_code == 201
    assert usage(session_factory) == 2
    denied = client.post("/api/v1/approvals", json=draft_body())
    assert denied.status_code == 429
    assert denied.json()["error"]["code"] == "DEMO_WRITE_LIMIT_REACHED"
    assert "no-store" in denied.headers["cache-control"]
    assert usage(session_factory) == 2
    assert client.get("/api/v1/employees/me").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/employees/me").status_code == 401
    set_actor(client, "emp_eng_001")
    assert client.post("/api/v1/approvals", json=draft_body()).status_code == 201
    assert usage(session_factory, "demo_b") == 1


def test_other_workspace_cannot_read_change_submit_or_approve(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    setup_workspaces(session_factory)
    set_actor(client, "emp_sales_001")
    created = client.post("/api/v1/approvals", json=draft_body())
    assert created.status_code == 201
    item = created.json()
    path = "/api/v1/approvals/" + item["id"]
    set_actor(client, "emp_eng_001")
    assert client.get("/api/v1/approvals?scope=mine").json()["items"] == []
    assert client.get(path).status_code == 403
    assert client.patch(path, json={**draft_body(), "version": item["version"]}).status_code == 403
    assert client.post(path + "/submit", json={"version": item["version"]}).status_code == 403
    set_actor(client, "emp_sales_001")
    submitted = client.post(path + "/submit", json={"version": item["version"]})
    assert submitted.status_code == 200
    version = submitted.json()["version"]
    set_actor(client, "emp_eng_mgr_001")
    assert client.get("/api/v1/approvals?scope=assigned").json()["items"] == []
    assert client.post(path + "/approve", json={"version": version}).status_code == 403
    set_actor(client, "emp_sales_mgr_001")
    assert client.get("/api/v1/approvals?scope=assigned").json()["total"] == 1
    assert client.post(path + "/approve", json={"version": version}).status_code == 200


def test_other_workspace_cannot_access_agent_run(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    setup_workspaces(session_factory)
    set_actor(client, "emp_sales_001")
    created = client.post("/api/v1/leave-agent/runs", json={"request": "Synthetic leave request"})
    assert created.status_code == 201
    run_id = created.json()["run"]["id"]
    set_actor(client, "emp_eng_001")
    path = "/api/v1/leave-agent/runs/" + run_id
    assert client.get(path).status_code == 403
    assert client.post(path + "/consultation/retry").status_code == 403


def test_private_employee_without_workspace_keeps_organization_access(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    result = client.get("/api/v1/departments")
    assert result.status_code == 200
    assert len(result.json()) > 1


def test_database_failure_is_safe_and_does_not_admit(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_workspaces(session_factory)

    def broken_clock(db: Session) -> Any:
        from sqlalchemy.exc import OperationalError

        raise OperationalError("synthetic query", {}, Exception("synthetic private database value"))

    monkeypatch.setattr(demo_workspace, "_database_epoch", broken_clock)
    set_actor(client, "emp_sales_001")
    response = client.post("/api/v1/approvals", json=draft_body())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEMO_WORKSPACE_UNAVAILABLE"
    assert "private database value" not in response.text
    assert usage(session_factory) == 0


def test_expired_between_check_and_update_is_not_admitted(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import literal

    setup_workspaces(session_factory)
    with session_factory() as db:
        actor = db.get(Employee, "emp_sales_001")
        assert actor is not None
        expires = db.scalar(
            select(DemoWorkspace.expires_at_epoch).where(DemoWorkspace.id == "demo_a")
        )
        assert expires is not None
        times = iter([expires - 1, expires, expires])
        monkeypatch.setattr(demo_workspace, "_database_epoch", lambda db: literal(next(times)))
        from app.core.errors import AuthenticationError

        with pytest.raises(AuthenticationError):
            demo_workspace.require_demo_workspace(db, actor, write=True)
    assert usage(session_factory) == 0


def test_admission_refuses_to_commit_business_changes(
    session_factory: sessionmaker[Session],
) -> None:
    setup_workspaces(session_factory)
    with session_factory() as db:
        actor = db.get(Employee, "emp_sales_001")
        assert actor is not None
        actor.name = "Uncommitted synthetic edit"
        with pytest.raises(ValueError, match="precede business"):
            demo_workspace.require_demo_workspace(db, actor, write=True)


def test_department_with_nonmember_is_rejected(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    setup_workspaces(session_factory)
    with session_factory() as db:
        other = db.get(Employee, "emp_sales_002")
        assert other is not None
        other.demo_workspace_id = None
        db.commit()
    set_actor(client, "emp_sales_001")
    assert client.get("/api/v1/departments").status_code == 401


def test_imported_cross_workspace_approval_line_is_hidden_and_blocked(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    from app.models.approval import ApprovalLine

    setup_workspaces(session_factory)
    set_actor(client, "emp_sales_001")
    created = client.post("/api/v1/approvals", json=draft_body()).json()
    path = "/api/v1/approvals/" + created["id"]
    submitted = client.post(path + "/submit", json={"version": created["version"]})
    assert submitted.status_code == 200
    # Simulate a bad import or privileged DB edit; no public API assigns this relationship.
    with session_factory() as db:
        line = db.scalar(select(ApprovalLine).where(ApprovalLine.approval_id == created["id"]))
        assert line is not None
        line.approver_id = "emp_eng_mgr_001"
        db.commit()
    assert client.get("/api/v1/approvals?scope=mine").json()["items"] == []
    assert client.get(path).status_code == 403
    set_actor(client, "emp_eng_mgr_001")
    assert client.get("/api/v1/approvals?scope=assigned").json()["items"] == []
    assert client.get(path).status_code == 403
    assert client.post(path + "/approve", json={"version": 999}).status_code == 403


def test_read_only_ai_post_uses_quota_and_keeps_tool_identity(
    client: TestClient,
    session_factory: sessionmaker[Session],
    fake_work_assistant_provider: FakeWorkAssistantProvider,
) -> None:
    setup_workspaces(session_factory, limit=1)
    fake_work_assistant_provider.planned_calls = [("get_current_employee", {})]
    set_actor(client, "emp_sales_001")
    first = client.post("/api/v1/work-assistant/query", json={"message": "Synthetic self lookup"})
    assert first.status_code == 200
    assert first.json()["toolExecutions"][0]["result"]["employee"]["id"] == "emp_sales_001"
    assert usage(session_factory) == 1
    denied = client.post("/api/v1/work-assistant/query", json={"message": "Synthetic self lookup"})
    assert denied.status_code == 429
    assert len(fake_work_assistant_provider.messages) == 1
    set_actor(client, "emp_eng_001")
    other = client.post("/api/v1/work-assistant/query", json={"message": "Synthetic self lookup"})
    assert other.status_code == 200
    assert other.json()["toolExecutions"][0]["result"]["employee"]["id"] == "emp_eng_001"
    assert usage(session_factory, "demo_b") == 1


def test_department_schedule_and_team_leave_do_not_cross_workspaces(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    from datetime import date

    from app.models.attendance import WorkCalendarEvent
    from app.models.enums import (
        AttendanceEventCategory,
        AttendanceEventScope,
        AttendanceEventStatus,
        AttendanceImpact,
    )

    setup_workspaces(session_factory)
    with session_factory() as db:
        for name, department, teammate in [
            ("a", "dept_sales", "emp_sales_002"),
            ("b", "dept_engineering", "emp_eng_mgr_001"),
        ]:
            db.add(
                WorkCalendarEvent(
                    id="demo_schedule_" + name,
                    title="Synthetic schedule " + name,
                    category=AttendanceEventCategory.PROJECT_MILESTONE,
                    scope=AttendanceEventScope.DEPARTMENT,
                    department_id=department,
                    start_date=date(2026, 11, 10),
                    end_date=date(2026, 11, 10),
                    status=AttendanceEventStatus.CONFIRMED,
                    impact=AttendanceImpact.BLOCKED,
                )
            )
            db.add(
                WorkCalendarEvent(
                    id="demo_team_leave_" + name,
                    title="Synthetic leave " + name,
                    category=AttendanceEventCategory.LEAVE,
                    scope=AttendanceEventScope.EMPLOYEE,
                    employee_id=teammate,
                    start_date=date(2026, 11, 10),
                    end_date=date(2026, 11, 10),
                    status=AttendanceEventStatus.CONFIRMED,
                    impact=AttendanceImpact.CAUTION,
                )
            )
        db.commit()
    set_actor(client, "emp_sales_001")
    response = client.get(
        "/api/v1/attendance/overview",
        params={"startDate": "2026-11-01", "endDate": "2026-11-30"},
    )
    assert response.status_code == 200
    events = {item["id"] for item in response.json()["calendarEvents"]}
    team = {item["id"] for item in response.json()["teamLeaves"]}
    assert "demo_schedule_a" in events and "demo_schedule_b" not in events
    assert "demo_team_leave_a" in team and "demo_team_leave_b" not in team
    assert usage(session_factory) == 0

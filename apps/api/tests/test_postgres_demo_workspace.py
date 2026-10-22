"""Loopback-only PostgreSQL workspace admission; no hosted load experiment."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import AuthenticationError
from app.models.demo_workspace import DemoWorkspace
from app.models.employee import Department, Employee
from app.models.enums import EmployeeRole
from app.services import demo_workspace
from app.services.demo_workspace import DemoWriteLimitError, require_demo_workspace
from app.services.login_budget import database_seconds
from tests.test_postgres_approval_lists import session_factory as session_factory


def _setup(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        db.add(Department(id="demo_department", name="Independent synthetic demo"))
        db.flush()
        db.add(
            DemoWorkspace(
                id="demo_space",
                department_id="demo_department",
                expires_at_epoch=database_seconds(db) + 3600,
                is_active=True,
                write_limit=5,
                writes_used=0,
            )
        )
        db.flush()
        db.add(
            Employee(
                id="demo_actor",
                name="Synthetic visitor",
                email="visitor@jhworks.test",
                department_id="demo_department",
                demo_workspace_id="demo_space",
                position="Synthetic position",
                role=EmployeeRole.EMPLOYEE,
                hire_date=date(2026, 1, 1),
                leave_balance=0,
                is_active=True,
            )
        )
        db.commit()


def test_workspace_counter_cannot_over_admit(session_factory: sessionmaker[Session]) -> None:
    _setup(session_factory)
    barrier = Barrier(8)

    def attempt(_: int) -> bool:
        barrier.wait(timeout=20)
        with session_factory() as db:
            actor = db.get(Employee, "demo_actor")
            assert actor is not None
            try:
                require_demo_workspace(db, actor, write=True)
                return True
            except DemoWriteLimitError:
                return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        admitted = sum(executor.map(attempt, range(24)))
    assert admitted == 5
    with session_factory() as db:
        row = db.get(DemoWorkspace, "demo_space")
        assert row is not None and row.writes_used == 5
        actor = db.get(Employee, "demo_actor")
        assert actor is not None
        require_demo_workspace(db, actor)  # Reads remain available.


def test_revoked_during_admission_cannot_write(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup(session_factory)
    ready = Event()
    original = demo_workspace._database_epoch

    def attempt() -> None:
        calls = 0

        def clock(db: Session):  # type: ignore[no-untyped-def]
            nonlocal calls
            calls += 1
            if calls == 2:
                ready.set()
            return original(db)

        monkeypatch.setattr(demo_workspace, "_database_epoch", clock)
        with session_factory() as db:
            actor = db.get(Employee, "demo_actor")
            assert actor is not None
            with pytest.raises(AuthenticationError):
                require_demo_workspace(db, actor, write=True)

    with session_factory() as locked:
        locked.execute(
            update(DemoWorkspace).where(DemoWorkspace.id == "demo_space").values(is_active=False)
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(attempt)
            assert ready.wait(timeout=20)
            locked.commit()
            future.result(timeout=20)
    with session_factory() as db:
        assert db.scalar(select(DemoWorkspace.writes_used)) == 0


def test_postgres_cross_workspace_line_is_filtered_before_response(
    client: "TestClient",
    session_factory: sessionmaker[Session],
) -> None:
    from app.models.approval import ApprovalLine
    from app.models.enums import ApprovalLineStatus
    from tests.test_demo_workspace import draft_body, set_actor

    _setup(session_factory)
    set_actor(client, "demo_actor")
    created = client.post("/api/v1/approvals", json=draft_body())
    assert created.status_code == 201
    with session_factory() as db:
        outsider = db.scalars(select(Employee).where(Employee.demo_workspace_id.is_(None))).first()
        assert outsider is not None
        db.add(
            ApprovalLine(
                id="cross_workspace_line",
                approval_id=created.json()["id"],
                step=1,
                round=1,
                approver_id=outsider.id,
                status=ApprovalLineStatus.PENDING,
            )
        )
        db.commit()
    response = client.get("/api/v1/approvals?scope=mine")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}
    assert client.get("/api/v1/approvals/" + created.json()["id"]).status_code == 403

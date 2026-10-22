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


def test_concurrent_demo_creation_keeps_daily_and_retained_caps(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import func

    from app.core.config import Settings
    from app.models.demo_start_budget import DemoStartBudget
    from app.services import demo_visitor

    settings = Settings(
        _env_file=None,
        public_demo_enabled=True,
        ai_enabled=False,
        demo_starts_per_day=5,
        demo_retained_workspaces=3,
    )
    monkeypatch.setattr(demo_visitor, "database_seconds", lambda db: 1700000000)
    barrier = Barrier(8)

    def attempt(_: int) -> bool:
        barrier.wait(timeout=20)
        with session_factory() as db:
            try:
                demo_visitor.start_visit_safely(db, settings, None)
                return True
            except demo_visitor.DemoStartLimitError:
                return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(attempt, range(8))) == 3
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DemoWorkspace)) == 3
        assert db.scalar(select(DemoStartBudget.starts_used)) == 5


def test_postgres_all_request_budget_is_atomic(session_factory: sessionmaker[Session]) -> None:
    from app.services.demo_workspace import DemoRequestLimitError

    _setup(session_factory)
    with session_factory() as db:
        db.execute(update(DemoWorkspace).values(request_limit=5))
        db.commit()
    barrier = Barrier(8)

    def attempt(_: int) -> bool:
        barrier.wait(timeout=20)
        with session_factory() as db:
            actor = db.get(Employee, "demo_actor")
            assert actor is not None
            try:
                require_demo_workspace(db, actor)
                return True
            except DemoRequestLimitError:
                return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(attempt, range(24))) == 5
    with session_factory() as db:
        row = db.get(DemoWorkspace, "demo_space")
        assert row is not None and row.requests_used == 5 and row.writes_used == 0


def test_postgres_cleanup_preserves_private_rows_and_respects_foreign_keys(
    session_factory: sessionmaker[Session],
) -> None:
    from sqlalchemy import func

    from app.core.config import Settings
    from app.schemas.approval import ApprovalCreate
    from app.services.approval import create_draft, submit_approval
    from app.services.demo_cleanup import cleanup_expired_demo
    from app.services.demo_visitor import start_visit_safely

    with session_factory() as db:
        before = db.scalar(select(func.count()).select_from(Employee))
        actor = start_visit_safely(db, Settings(_env_file=None), None)
        employee_id, workspace_id = actor.id, actor.demo_workspace_id
        approval = create_draft(
            db,
            actor,
            ApprovalCreate.model_validate(
                {
                    "type": "GENERAL",
                    "title": "Synthetic FK cleanup",
                    "content": "Synthetic content",
                    "details": {"kind": "GENERAL"},
                }
            ),
        )
        submit_approval(db, actor, approval.id, approval.version)
        db.execute(
            update(DemoWorkspace)
            .where(DemoWorkspace.id == workspace_id)
            .values(expires_at_epoch=database_seconds(db) - 86401)
        )
        db.commit()
    with session_factory() as db:
        assert cleanup_expired_demo(db, apply=True).removed == 1
    with session_factory() as db:
        assert db.get(Employee, employee_id) is None
        assert db.scalar(select(func.count()).select_from(Employee)) == before


def test_feedback_global_capacity_is_atomic(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import func

    from app.core.config import Settings
    from app.core.errors import AppError
    from app.models.demo_feedback import DemoFeedback
    from app.schemas.demo_feedback import DemoFeedbackCreate
    from app.services import demo_feedback
    from app.services.demo_visitor import start_visit_safely

    monkeypatch.setattr(demo_feedback, "MAX_FEEDBACK", 3)
    ids = []
    for _ in range(8):
        with session_factory() as db:
            ids.append(start_visit_safely(db, Settings(_env_file=None), None).id)
    barrier = Barrier(8)
    payload = DemoFeedbackCreate(
        category="bug",
        screen="general",
        message="Synthetic concurrent feedback for a test",
        consent=True,
    )

    def attempt(employee_id: str) -> bool:
        barrier.wait(timeout=20)
        with session_factory() as db:
            actor = db.get(Employee, employee_id)
            assert actor is not None
            try:
                demo_feedback.submit_feedback(db, actor, payload)
                return True
            except AppError as exc:
                assert exc.code == "DEMO_FEEDBACK_CAPACITY"
                return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(attempt, ids)) == 3
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DemoFeedback)) == 3


def test_feedback_concurrent_retries_return_one_receipt(
    session_factory: sessionmaker[Session],
) -> None:
    from sqlalchemy import func

    from app.core.config import Settings
    from app.models.demo_feedback import DemoFeedback
    from app.schemas.demo_feedback import DemoFeedbackCreate
    from app.services.demo_feedback import submit_feedback
    from app.services.demo_visitor import start_visit_safely

    with session_factory() as db:
        employee_id = start_visit_safely(db, Settings(_env_file=None), None).id
    barrier = Barrier(8)
    payload = DemoFeedbackCreate(
        category="idea",
        screen="general",
        message="Synthetic retry feedback for a test",
        consent=True,
    )

    def attempt(_: int) -> str:
        barrier.wait(timeout=20)
        with session_factory() as db:
            actor = db.get(Employee, employee_id)
            assert actor is not None
            return submit_feedback(db, actor, payload).id

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert len(set(executor.map(attempt, range(8)))) == 1
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DemoFeedback)) == 1


def test_feedback_concurrent_retention_counts_each_deletion_once(
    session_factory: sessionmaker[Session],
) -> None:
    from app.services.demo_feedback import purge_expired_feedback
    from tests.test_feedback_retention import add_feedback

    with session_factory() as db:
        for index in range(3):
            add_feedback(db, f"expired_{index}", 1)
        db.commit()
    barrier = Barrier(8)

    def attempt(_: int) -> int:
        barrier.wait(timeout=20)
        with session_factory() as db:
            result = purge_expired_feedback(db, apply=True)
            assert result.stored == 0
            return result.removed

    with ThreadPoolExecutor(max_workers=8) as executor:
        counts = list(executor.map(attempt, range(8)))
    assert sorted(counts) == [0] * 7 + [3]


def test_maintenance_runner_on_postgres_preserves_private_rows(
    session_factory: sessionmaker[Session],
) -> None:
    from sqlalchemy import func

    from app.core.config import Settings
    from app.ops.demo_maintenance import run_maintenance
    from app.services.demo_visitor import start_visit_safely
    from tests.test_feedback_retention import add_feedback

    with session_factory() as db:
        before = db.scalar(select(func.count()).select_from(Employee))
        actor = start_visit_safely(db, Settings(_env_file=None), None)
        workspace_id = actor.demo_workspace_id
        db.execute(
            update(DemoWorkspace)
            .where(DemoWorkspace.id == workspace_id)
            .values(
                expires_at_epoch=database_seconds(db) - 86401,
            )
        )
        add_feedback(db, "synthetic_expired_feedback", 1)
        db.commit()
    report = run_maintenance(session_factory, apply=True)
    assert report["status"] == "passed"
    assert report["steps"]["feedback"]["removed"] == 1
    assert report["steps"]["workspaces"]["removed"] == 1
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Employee)) == before
    again = run_maintenance(session_factory, apply=True)
    assert again["steps"]["feedback"]["removed"] == 0
    assert again["steps"]["workspaces"]["removed"] == 0


def test_maintenance_postgres_transaction_timeouts(session_factory: sessionmaker[Session]) -> None:
    from sqlalchemy import event, text

    from app.ops.demo_maintenance import transaction_timeouts

    with session_factory() as db:
        event.listen(db, "after_begin", transaction_timeouts)
        assert db.scalar(text("SHOW statement_timeout")) == "15s"
        assert db.scalar(text("SHOW lock_timeout")) == "5s"

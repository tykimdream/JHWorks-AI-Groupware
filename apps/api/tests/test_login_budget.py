import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes import auth
from app.core.config import get_settings
from app.core.errors import RateLimitError
from app.models.login_budget import LoginBudget
from app.services import login_budget


def test_unknown_accounts_share_login_budget(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings().model_copy(update={"login_requests_per_minute": 2})
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    for i in range(2):
        result = client.post(
            "/api/v1/auth/login",
            json={
                "email": f"unknown{i}@jhworks.test",
                "password": "synthetic-invalid",
            },
        )
        assert result.status_code == 401
    blocked = client.post(
        "/api/v1/auth/login",
        json={
            "email": "another@jhworks.test",
            "password": "synthetic-invalid",
        },
        headers={"X-Forwarded-For": "192.0.2.99"},
    )
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "60"
    assert blocked.headers["Cache-Control"] == "private, no-store"
    assert "set-cookie" not in blocked.headers


def test_budget_blocks_before_password_verification(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(update={"login_requests_per_minute": 2})
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    attempts: list[str] = []

    def verify(password: str, password_hash: str) -> bool:
        attempts.append(password)
        return False

    monkeypatch.setattr(auth, "verify_password", verify)
    for _ in range(3):
        client.post(
            "/api/v1/auth/login",
            json={
                "email": "seojin.yoon@jhworks.test",
                "password": "synthetic-invalid",
            },
        )
    assert len(attempts) == 2


def test_window_recovery_and_clock_regression(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seconds = [120]
    monkeypatch.setattr(login_budget, "database_seconds", lambda db: seconds[0])
    with session_factory() as db:
        login_budget.reserve_login_attempt(db, 1)
    with session_factory() as db, pytest.raises(RateLimitError):
        login_budget.reserve_login_attempt(db, 1)
    seconds[0] = 180
    with session_factory() as db:
        login_budget.reserve_login_attempt(db, 1)
    seconds[0] = 120
    with session_factory() as db, pytest.raises(RateLimitError):
        login_budget.reserve_login_attempt(db, 1)
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(LoginBudget)) == 1
        row = db.get(LoginBudget, 1)
        assert row is not None and row.window == 3 and row.attempts == 1


def test_existing_session_and_logout_remain_available(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(update={"login_requests_per_minute": 1})
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(login_budget, "database_seconds", lambda db: 120)
    result = client.post(
        "/api/v1/auth/login",
        json={
            "email": "seojin.yoon@jhworks.test",
            "password": "demo1234",
        },
    )
    assert result.status_code == 200
    blocked = client.post(
        "/api/v1/auth/login",
        json={
            "email": "unknown@jhworks.test",
            "password": "synthetic-invalid",
        },
    )
    assert blocked.status_code == 429 and "set-cookie" not in blocked.headers
    assert client.get("/api/v1/employees/me").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/employees/me").status_code == 401


def test_database_failure_fails_closed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_clock(db: Session) -> int:
        raise OperationalError("synthetic clock failure", None, RuntimeError("synthetic"))

    def must_not_verify(password: str, password_hash: str) -> bool:
        raise AssertionError("password verification must not run")

    monkeypatch.setattr(login_budget, "database_seconds", broken_clock)
    monkeypatch.setattr(auth, "verify_password", must_not_verify)
    result = client.post(
        "/api/v1/auth/login",
        json={
            "email": "seojin.yoon@jhworks.test",
            "password": "synthetic-invalid",
        },
    )
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "LOGIN_BUDGET_UNAVAILABLE"
    assert "synthetic" not in result.text and "set-cookie" not in result.headers
    assert result.headers["Cache-Control"] == "private, no-store"


def test_database_clock_is_used(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        assert login_budget.database_seconds(db) > 0


def test_budget_does_not_commit_existing_work(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        db.add(LoginBudget(id=1, window=2, attempts=1))
        with pytest.raises(ValueError, match="fresh request session"):
            login_budget.reserve_login_attempt(db, 2)
        db.rollback()
    with session_factory() as db:
        assert db.get(LoginBudget, 1) is None

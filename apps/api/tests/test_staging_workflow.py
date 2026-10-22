import getpass
import json
import sys
from collections.abc import Generator
from contextlib import ExitStack, contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import app
from app.models import Approval, LeaveAccount
from app.ops import staging_workflow
from app.ops.staging_fixture import populate
from app.ops.staging_password import rotate_passwords
from app.ops.staging_workflow import ACTORS, ORIGIN, HttpClient, Workflow

PASSWORD = "synthetic-workflow-test-only-password"


@pytest.fixture
def workflow(monkeypatch: pytest.MonkeyPatch) -> Generator[Workflow, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        populate(db, PASSWORD, 2026)

    def database() -> Generator[Session, None, None]:
        with Session(engine) as db:
            yield db

    settings = get_settings()
    monkeypatch.setattr(settings, "frontend_origin", ORIGIN)
    monkeypatch.setattr(settings, "cookie_secure", True)
    app.dependency_overrides[get_db] = database
    try:
        with ExitStack() as stack:
            clients: dict[str, HttpClient] = {
                actor: stack.enter_context(TestClient(app, base_url=ORIGIN,
                                                       headers={"Origin": ORIGIN}))
                for actor in ACTORS
            }
            yield Workflow(clients)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_real_routes_auth_permissions_versions_and_leave_transaction(workflow: Workflow) -> None:
    workflow.execute(PASSWORD, 2026)
    assert "confirmed_leave_calendar" in workflow.passed
    assert all(f"{kind}_unrelated_decide" in workflow.passed for kind in ["general", "leave"])
    assert all("login_" + actor + "_secure_cookie" in workflow.passed for actor in ACTORS)
    with next_database() as db:
        assert db.scalar(select(func.count()).select_from(Approval)) == 2
        assert sum(account.used_days for account in db.scalars(select(LeaveAccount))) == 1
    with pytest.raises(ValueError, match="check failed"):
        workflow.execute(PASSWORD, 2026)
    assert workflow.stage == "empty_author_mine"
    with next_database() as db:
        assert db.scalar(select(func.count()).select_from(Approval)) == 2


@contextmanager
def next_database() -> Generator[Session, None, None]:
    # Use the same dependency that the real routes use, without reading credential rows.
    yield from app.dependency_overrides[get_db]()


def test_wrong_password_stops_before_any_business_write(workflow: Workflow) -> None:
    with pytest.raises(ValueError):
        workflow.execute("synthetic-wrong-password", 2026)
    assert workflow.stage == "login_author"
    with next_database() as db:
        assert db.scalar(select(func.count()).select_from(Approval)) == 0


def test_replaced_fixture_password_completes_real_workflow(workflow: Workflow) -> None:
    replacement = PASSWORD + "-replacement"
    with next_database() as db, db.begin():
        rotate_passwords(db, replacement, 2026)
    workflow.execute(replacement, 2026)
    assert "confirmed_leave_calendar" in workflow.passed


def test_cli_apply_uses_only_hidden_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    def no_plaintext_input(*_args: object) -> None:
        raise AssertionError("plaintext input is forbidden")

    def execute(_self: Workflow, password: str, _commit: str) -> None:
        assert password == PASSWORD
        calls.append("remote")

    monkeypatch.setattr(staging_workflow, "verify_private_service", lambda _commit: None)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", no_plaintext_input)
    monkeypatch.setattr(getpass, "getpass", lambda _prompt: PASSWORD)
    monkeypatch.setattr(Workflow, "run_remote", execute)
    monkeypatch.setattr(sys, "argv", ["workflow", "--commit", "a" * 40, "--apply"])
    staging_workflow.main()
    assert calls == ["remote"]
    assert PASSWORD not in capsys.readouterr().out


def test_http_redirect_is_failure_and_not_retried() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(307, headers={"Location": "https://untrusted.invalid"})

    with httpx.Client(base_url=ORIGIN, transport=httpx.MockTransport(handler)) as client:
        workflow = Workflow({actor: client for actor in ACTORS})
        with pytest.raises(ValueError):
            workflow.execute(PASSWORD, 2026)
    assert calls == [ORIGIN + "/api/v1/auth/login"]


def test_timeout_is_not_retried() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    with httpx.Client(base_url=ORIGIN, transport=httpx.MockTransport(handler)) as client:
        workflow = Workflow({actor: client for actor in ACTORS})
        with pytest.raises(httpx.ReadTimeout):
            workflow.execute(PASSWORD, 2026)
    assert len(calls) == 1
    assert workflow.stage == "login_author"


def test_cli_failure_does_not_print_raw_exception_or_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(_commit: str) -> None:
        raise ValueError("synthetic-sensitive-token-and-password")

    monkeypatch.setattr(staging_workflow, "verify_private_service", fail)
    monkeypatch.setattr(sys, "argv", ["workflow", "--commit", "a" * 40])
    with pytest.raises(SystemExit) as failure:
        staging_workflow.main()
    assert failure.value.code == 1
    result = capsys.readouterr().out
    assert json.loads(result) == {
        "status": "failed", "stage": "service_verify", "errorType": "ValueError", "checks": [],
    }
    assert "synthetic-sensitive-token-and-password" not in result


def test_cli_defaults_to_no_credentials_and_no_writes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def unexpected(*_args: object) -> None:
        raise AssertionError("must not ask for credentials or run workflows")

    monkeypatch.setattr(staging_workflow, "verify_private_service", lambda _commit: None)
    monkeypatch.setattr(getpass, "getpass", unexpected)
    monkeypatch.setattr(staging_workflow.Workflow, "run_remote", unexpected)
    monkeypatch.setattr(sys, "argv", ["workflow", "--commit", "a" * 40])
    staging_workflow.main()
    assert json.loads(capsys.readouterr().out) == {
        "status": "passed", "mode": "service-preflight", "changed": 0,
    }


def test_cli_noninteractive_apply_refuses_before_credential_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(staging_workflow, "verify_private_service", lambda _commit: None)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(sys, "argv", ["workflow", "--commit", "a" * 40, "--apply"])
    with pytest.raises(SystemExit):
        staging_workflow.main()
    assert json.loads(capsys.readouterr().out)["stage"] == "operator_confirmation"

import json
import sys
from collections.abc import Generator
from decimal import Decimal

import pytest
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.security import verify_password
from app.models import Approval, Credential, Department, Employee, LeaveAccount
from app.models.enums import ApprovalStatus, ApprovalType
from app.ops import staging_password
from app.ops.staging_fixture import IDS, populate
from app.ops.staging_password import rotate_passwords

OLD = "synthetic-old-test-password-only"
NEW = "synthetic-new-test-password-only"


@pytest.fixture
def fixture_engine() -> Generator[Engine, None, None]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        populate(db, OLD, 2026)
    try:
        yield engine
    finally:
        engine.dispose()


def test_rotate_exact_fixture_rejects_old_password_and_preserves_business_rows(
    fixture_engine: Engine,
) -> None:
    with Session(fixture_engine) as db, db.begin():
        rotate_passwords(db, NEW, 2026)
    with Session(fixture_engine) as db:
        credentials = list(db.scalars(select(Credential)))
        assert {c.employee_id for c in credentials} == set(IDS)
        assert len({c.password_hash for c in credentials}) == 3
        assert all(verify_password(NEW, c.password_hash) for c in credentials)
        assert not any(verify_password(OLD, c.password_hash) for c in credentials)
        assert list(db.scalars(select(Approval))) == []
        assert all(a.available_days == 15 and a.version == 1
                   for a in db.scalars(select(LeaveAccount)))


@pytest.mark.parametrize("password", [OLD, "demo1234", " " + NEW, "x" * 129])
def test_reused_or_invalid_password_preserves_all_credentials(
    fixture_engine: Engine, password: str,
) -> None:
    with pytest.raises(ValueError), Session(fixture_engine) as db, db.begin():
        rotate_passwords(db, password, 2026)
    with Session(fixture_engine) as db:
        assert all(verify_password(OLD, c.password_hash) for c in db.scalars(select(Credential)))


@pytest.mark.parametrize("change", ["employee", "leave", "department", "approval"])
def test_changed_fixture_refuses_any_credential_mutation(
    fixture_engine: Engine, change: str,
) -> None:
    with Session(fixture_engine) as db, db.begin():
        if change == "employee":
            employee = db.get(Employee, IDS[0])
            assert employee is not None
            employee.email = "different.synthetic@jhworks.test"
        elif change == "leave":
            account = db.scalar(select(LeaveAccount).where(LeaveAccount.employee_id == IDS[0]))
            assert account is not None
            account.used_days = Decimal("1")
        elif change == "department":
            db.add(Department(id="extra_synthetic", name="extra synthetic"))
        else:
            db.add(Approval(id="synthetic_existing", author_id=IDS[0], type=ApprovalType.GENERAL,
                            title="Synthetic existing work", content="Synthetic",
                            status=ApprovalStatus.DRAFT, details={"kind": "GENERAL"},
                            attachment_metadata=[]))
    with pytest.raises(ValueError), Session(fixture_engine) as db, db.begin():
        rotate_passwords(db, NEW, 2026)
    with Session(fixture_engine) as db:
        assert all(verify_password(OLD, c.password_hash) for c in db.scalars(select(Credential)))


def test_hash_failure_rolls_back_all_three_credentials(
    fixture_engine: Engine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fail(_password: str) -> str:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic hash failure")
        return "synthetic-incomplete-replacement"

    monkeypatch.setattr(staging_password, "hash_password", fail)
    with pytest.raises(RuntimeError), Session(fixture_engine) as db, db.begin():
        rotate_passwords(db, NEW, 2026)
    with Session(fixture_engine) as db:
        assert all(verify_password(OLD, c.password_hash) for c in db.scalars(select(Credential)))


def test_cli_reports_safe_stage_without_password_or_hash(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(_commit: str) -> None:
        raise ValueError("synthetic-private-password-and-hash")

    monkeypatch.setattr(staging_password, "verify_private_service", fail)
    monkeypatch.setattr(sys, "argv", ["password", "--commit", "a" * 40,
                                      "--ca-file", "synthetic-ca.crt"])
    with pytest.raises(SystemExit):
        staging_password.main()
    result = capsys.readouterr().out
    assert json.loads(result) == {"status": "failed", "stage": "service_verify",
                                 "errorType": "ValueError", "rotatedCredentials": 0}
    assert "synthetic-private-password-and-hash" not in result

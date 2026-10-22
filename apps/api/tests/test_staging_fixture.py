import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.security import verify_password
from app.models import Credential, Department, Employee, LeaveAccount
from app.ops import staging_fixture
from app.ops.staging_fixture import HEAD, IDS, populate, verify_backup


def test_private_fixture_populates_only_three_synthetic_accounts_and_refuses_replay() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    password = "synthetic-test-only-long-password"
    try:
        with Session(engine) as db, db.begin():
            populate(db, password, 2026)
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Department)) == 1
            assert db.scalar(select(func.count()).select_from(Employee)) == 3
            assert db.scalar(select(func.count()).select_from(LeaveAccount)) == 3
            employees = {e.id: e for e in db.scalars(select(Employee))}
            assert employees[IDS[0]].manager_id == IDS[1]
            assert employees[IDS[2]].manager_id == IDS[1]
            for credential in db.scalars(select(Credential)):
                assert credential.password_hash != password
                assert verify_password(password, credential.password_hash)
        with Session(engine) as db, db.begin(), pytest.raises(ValueError, match="empty"):
            populate(db, password, 2026)
    finally:
        engine.dispose()


def test_weak_fixture_password_writes_nothing() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db, db.begin(), pytest.raises(ValueError, match="20 to 128"):
            populate(db, "demo1234", 2026)
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Department)) == 0
    finally:
        engine.dispose()


def test_failed_credential_creation_rolls_back_department_and_employees(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    def fail_hash(_password: str) -> str:
        raise RuntimeError("synthetic hash failure")

    monkeypatch.setattr(staging_fixture, "hash_password", fail_hash)
    try:
        with pytest.raises(RuntimeError), Session(engine) as db, db.begin():
            populate(db, "synthetic-test-only-long-password", 2026)
        with Session(engine) as db:
            for model in [Department, Employee, Credential, LeaveAccount]:
                assert db.scalar(select(func.count()).select_from(model)) == 0
    finally:
        engine.dispose()


def test_backup_must_match_real_verified_archive(tmp_path: Path) -> None:
    stamp = "20261021T144435Z-c266bd9d"
    archive = b"synthetic archive bytes"
    digest = hashlib.sha256(archive).hexdigest()
    reference = f"cloud-shell:{stamp}:sha256:{digest}:restore-verified"
    directory = tmp_path / stamp
    directory.mkdir()
    (directory / "groupware.dump").write_bytes(archive)
    (directory / "verification.json").write_text(json.dumps({
        "status": "passed", "temporaryContainerRemoved": True, "head": HEAD,
        "backupReference": reference, "dumpSha256": digest,
    }), encoding="utf-8")
    verify_backup(reference, tmp_path)
    (directory / "groupware.dump").write_bytes(b"changed")
    with pytest.raises(ValueError, match="does not match"):
        verify_backup(reference, tmp_path)


@pytest.mark.parametrize("change", [None, "public", "iam_disabled", "wrong_revision", "ai"])
def test_private_fixture_service_boundary(
    change: str | None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision = "jhworks-staging-" + "a" * 12
    service: dict[str, Any] = {
        "metadata": {"annotations": {"run.googleapis.com/maxScale": "2"}},
        "status": {"latestReadyRevisionName": revision,
                   "traffic": [{"revisionName": revision, "percent": 100}]},
        "spec": {"template": {"spec": {"containers": [{"name": "api", "env": [
            {"name": "JHWORKS_AI_ENABLED", "value": "true" if change == "ai" else "false"},
        ]}]}}},
    }
    if change == "iam_disabled":
        service["metadata"]["annotations"]["run.googleapis.com/invoker-iam-disabled"] = "true"
    if change == "wrong_revision":
        service["status"]["latestReadyRevisionName"] = "another-revision"

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "describe" in command:
            payload = {"projectNumber": "968398406137"} if command[1] == "projects" else service
        else:
            payload = {"bindings": [{"members": ["allUsers"] if change == "public" else []}]}
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr(staging_fixture, "run", fake_run)
    if change is None:
        staging_fixture.verify_private_service("a" * 40)
    else:
        with pytest.raises(ValueError):
            staging_fixture.verify_private_service("a" * 40)

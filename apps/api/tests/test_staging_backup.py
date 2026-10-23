import json
import subprocess
from pathlib import Path
from typing import Any, NoReturn

import pytest

from app.ops import staging_backup

CA_FILE = Path(__file__).parents[3] / "deploy/cloud-run/supabase-ca-2021.crt"
URL = (
    "postgresql+psycopg://jhworks_migrate.uztfgtfvxhpmavybldbh:synthetic%40password"
    "@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres?sslmode=verify-full"
)
IMAGE = "pgvector/pgvector@sha256:" + "a" * 64
DEMO_URL = URL.replace("jhworks_migrate.", "jhworks_demo_migrate.")


def test_backup_uses_session_pooler_and_pinned_ca() -> None:
    parameters = staging_backup.connection_parameters(URL, CA_FILE)
    assert parameters["password"] == "synthetic@password"
    assert parameters["port"] == 5432
    assert parameters["sslmode"] == "verify-full"
    assert parameters["sslrootcert"] == str(CA_FILE)


def test_demo_profile_requires_its_own_migration_identity() -> None:
    profile = staging_backup.BackupProfile.DEMO
    parameters = staging_backup.connection_parameters(DEMO_URL, CA_FILE, profile=profile)
    assert parameters["user"] == "jhworks_demo_migrate.uztfgtfvxhpmavybldbh"
    assert parameters["password"] == "synthetic@password"
    for url, selected in ((URL, profile), (DEMO_URL, staging_backup.BackupProfile.STAGING)):
        with pytest.raises(ValueError, match="approved migration session pooler"):
            staging_backup.connection_parameters(url, CA_FILE, profile=selected)


def test_demo_catalog_queries_do_not_modify_staging_queries() -> None:
    original = staging_backup.CATALOG_QUERIES.copy()
    queries = staging_backup.catalog_queries(staging_backup.BackupProfile.DEMO)
    assert queries.keys() == original.keys()
    assert all("'groupware_demo'" in query and "'groupware'" not in query
               for query in queries.values())
    assert staging_backup.catalog_queries(staging_backup.BackupProfile.STAGING) == original
    assert original == staging_backup.CATALOG_QUERIES


def test_demo_backup_reads_only_demo_migration_secret_and_sanitizes_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[:3] == ["gcloud", "projects", "describe"]:
            return subprocess.CompletedProcess(command, 0, stdout="968398406137\n")
        raise subprocess.CalledProcessError(1, command, stderr="synthetic-private-credential")

    monkeypatch.setattr(staging_backup, "run", fake_run)
    report = staging_backup.rehearse(
        IMAGE, CA_FILE, tmp_path, profile=staging_backup.BackupProfile.DEMO,
    )
    assert commands == [
        ["gcloud", "projects", "describe", staging_backup.PROJECT, "--format=value(projectNumber)"],
        ["gcloud", "secrets", "versions", "access", "1", "--secret",
         "jhworks-demo-migration-database", "--project", staging_backup.PROJECT],
    ]
    assert report["status"] == "failed"
    assert report["profile"] == "demo" and report["schema"] == "groupware_demo"
    assert "synthetic-private" not in next(tmp_path.glob("*/verification.json")).read_text()


def test_arbitrary_profile_rejected_before_secret_or_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
        pytest.fail("invalid profile must not run commands")

    monkeypatch.setattr(staging_backup, "run", forbidden)
    with pytest.raises(ValueError, match="fixed backup profiles"):
        staging_backup.rehearse(IMAGE, CA_FILE, tmp_path, profile="foreign")  # type: ignore[arg-type]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("identity", "private_usage"),
    [(('jhworks_migrate', 'groupware_demo'), False),
     (('jhworks_demo_migrate', 'groupware_demo'), True)],
)
def test_demo_identity_or_private_access_leak_stops_before_dump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    identity: tuple[str, str], private_usage: bool,
) -> None:
    commands: list[list[str]] = []
    statements: list[str] = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        assert command[0] == "gcloud", "dump/restore must not start"
        output = "968398406137" if command[1] == "projects" else DEMO_URL
        return subprocess.CompletedProcess(command, 0, stdout=output)

    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def execute(self, statement: str) -> "Connection":
            statements.append(statement)
            return self

        def fetchone(self) -> tuple[Any, ...]:
            if statements[-1] == "SELECT current_user,current_schema()":
                return identity
            return (private_usage,)

    monkeypatch.setattr(staging_backup, "run", fake_run)
    monkeypatch.setattr("app.ops.staging_backup.psycopg.connect", lambda **kwargs: Connection())
    report = staging_backup.rehearse(
        IMAGE, CA_FILE, tmp_path, profile=staging_backup.BackupProfile.DEMO,
    )
    assert report["status"] == "failed" and report["stage"] == "dump"
    assert report["errorType"] == "ValueError"
    assert len(commands) == 2
    assert not list(tmp_path.glob("*/*.dump"))
    assert not any("pg_export_snapshot" in statement for statement in statements)


@pytest.mark.parametrize(
    "url",
    [
        URL.replace(":5432/", ":6543/"),
        URL.replace("verify-full", "require"),
        URL.replace("aws-0-ap-northeast-2.pooler.supabase.com", "foreign.test"),
        URL.replace("jhworks_migrate", "jhworks_runtime"),
        URL.replace("/postgres?", "/another_database?"),
    ],
)
def test_backup_rejects_other_database_or_weaker_tls(url: str) -> None:
    with pytest.raises(ValueError, match="approved migration session pooler"):
        staging_backup.connection_parameters(url, CA_FILE)


def test_backup_rejects_changed_ca(tmp_path: Path) -> None:
    ca = tmp_path / "foreign-ca.crt"
    ca.write_text("synthetic wrong CA")
    with pytest.raises(ValueError, match="CA checksum"):
        staging_backup.connection_parameters(URL, ca)


def test_fingerprint_ignores_row_order_but_not_changed_rows_or_boundaries() -> None:
    fingerprint = staging_backup.rows_fingerprint
    assert fingerprint(['{"id":1}', '{"id":2}']) == fingerprint(['{"id":2}', '{"id":1}'])
    assert fingerprint(['{"id":1}']) != fingerprint(['{"id":2}'])
    assert fingerprint(["a", "bc"]) != fingerprint(["ab", "c"])


def test_large_rehearsal_requires_resource_review_before_exporting_rows() -> None:
    queries: list[str] = []

    def query(statement: str) -> Any:
        queries.append(statement)
        if "FROM pg_tables" in statement:
            return ["alembic_version"]
        if "to_jsonb(count(*))" in statement:
            return staging_backup.ROW_LIMIT + 1
        return []

    with pytest.raises(ValueError, match="row limit exceeded"):
        staging_backup.snapshot(query)
    assert any(f"LIMIT {staging_backup.ROW_LIMIT + 1}" in statement for statement in queries)
    assert not any("to_jsonb(t)::text" in statement for statement in queries)


def test_mutable_image_does_not_create_backup_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="image digest"):
        staging_backup.rehearse("pgvector/pgvector:pg17", CA_FILE, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_sequence_state_is_read_without_converting_pseudorelation_to_composite() -> None:
    def query(statement: str) -> Any:
        if "FROM pg_tables" in statement:
            return ["alembic_version"]
        if "to_jsonb(count(*))" in statement:
            return 0
        if "FROM pg_sequences" in statement:
            return ["display_number_seq"]
        if 'FROM "groupware"."display_number_seq"' in statement:
            assert "to_jsonb(t)" not in statement
            assert "'last_value',last_value,'is_called',is_called" in statement
            return {"last_value": 1, "is_called": False}
        if "to_jsonb(version_num)" in statement:
            return "synthetic-head"
        return []

    observed = staging_backup.snapshot(query)
    assert observed["sequences"] == {"display_number_seq": {"last_value": 1, "is_called": False}}


def test_failure_report_never_includes_credentials_or_command_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: Any, **kwargs: Any) -> NoReturn:
        raise subprocess.CalledProcessError(
            1, ["synthetic-command"], stderr="synthetic-private-credential"
        )

    monkeypatch.setattr(staging_backup, "run", fail)
    report = staging_backup.rehearse(IMAGE, CA_FILE, tmp_path)
    assert report["status"] == "failed"
    assert report["stage"] == "preflight"
    assert report["errorType"] == "CalledProcessError"
    assert "synthetic-private" not in json.dumps(report)
    assert "backupReference" not in report
    stored = next(tmp_path.glob("*/verification.json")).read_text()
    assert "synthetic-private" not in stored

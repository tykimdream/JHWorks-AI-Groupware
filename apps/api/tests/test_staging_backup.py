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


def test_backup_uses_session_pooler_and_pinned_ca() -> None:
    parameters = staging_backup.connection_parameters(URL, CA_FILE)
    assert parameters["password"] == "synthetic@password"
    assert parameters["port"] == 5432
    assert parameters["sslmode"] == "verify-full"
    assert parameters["sslrootcert"] == str(CA_FILE)


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

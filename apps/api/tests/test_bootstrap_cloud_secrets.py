import subprocess
from unittest.mock import MagicMock

import pytest
from psycopg import OperationalError, errors

from app.ops import bootstrap_cloud_secrets as setup


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (OperationalError("certificate verify failed secret_value"), "DB_TLS_FAILED"),
        (OperationalError("could not translate host secret_value"), "DB_DNS_FAILED"),
        (OperationalError("connection timed out secret_value"), "DB_CONNECTION_TIMEOUT"),
        (errors.InvalidPassword("secret_value"), "DB_AUTHENTICATION_FAILED"),
        (errors.InsufficientPrivilege("secret_value"), "DB_ROLE_PERMISSION_DENIED"),
    ],
)
def test_safe_failure_code_never_exposes_diagnostics(error: Exception, expected: str) -> None:
    result = setup.safe_failure_code(error)
    assert result == expected
    assert "secret_value" not in result


def test_preflight_failure_happens_before_password_prompt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "setup",
            "--project=synthetic-project",
            "--project-ref=" + "a" * 20,
            "--pooler-host=aws-0-ap-northeast-2.pooler.supabase.com",
            "--confirm-new-private-staging",
        ],
    )
    monkeypatch.setattr("app.ops.bootstrap_cloud_secrets.shutil.which", lambda name: "/bin/gcloud")
    monkeypatch.setattr("app.ops.bootstrap_cloud_secrets.Path.is_file", lambda path: True)
    password_prompt = MagicMock()
    monkeypatch.setattr("app.ops.bootstrap_cloud_secrets.getpass.getpass", password_prompt)
    monkeypatch.setattr(
        setup, "ensure_empty_targets", MagicMock(side_effect=RuntimeError("secret_value"))
    )
    assert setup.main() == 1
    password_prompt.assert_not_called()
    assert "secret_value" not in capsys.readouterr().out


def test_url_encodes_password_and_verifies_tls() -> None:
    url = setup.database_url("jhworks_runtime", "a" * 20, "@%:/?#", "pooler.example", 6543)
    assert ":%40%25%3A%2F%3F%23@" in url
    assert "sslmode=verify-full" in url
    assert "sslrootcert=/workspace/certs/supabase-ca-2021.crt" in url


def test_existing_services_or_secret_versions_block_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup, "run_command", lambda *args, **kwargs: b"existing")
    with pytest.raises(RuntimeError, match="without Cloud Run"):
        setup.ensure_empty_targets("synthetic-project")
    outputs = iter([b"", b"version-1"])
    monkeypatch.setattr(setup, "run_command", lambda *args, **kwargs: next(outputs))
    with pytest.raises(RuntimeError, match="without existing versions"):
        setup.ensure_empty_targets("synthetic-project")


def test_setup_uses_stdin_and_hides_all_credential_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[list[str], bytes | None, dict[str, str] | None]] = []

    def run(
        arguments: list[str],
        *,
        payload: bytes | None = None,
        environment: dict[str, str] | None = None,
    ) -> bytes:
        calls.append((arguments, payload, environment))
        return b""

    tokens = iter(["runtime_value", "migration_value", "session_value"])
    password_setup = MagicMock()
    monkeypatch.setattr(setup, "run_command", run)
    monkeypatch.setattr(
        "app.ops.bootstrap_cloud_secrets.secrets.token_urlsafe", lambda length: next(tokens)
    )
    monkeypatch.setattr(setup, "set_role_passwords", password_setup)
    setup.bootstrap("synthetic-project", "a" * 20, "pooler.example", "admin_value")
    password_setup.assert_called_once()
    secret_calls = [call for call in calls if "add" in call[0]]
    assert len(secret_calls) == 3
    assert all(call[2] is None and "--data-file=-" in call[0] for call in secret_calls)
    output = capsys.readouterr().out + repr([call[0] for call in calls])
    for value in ("runtime_value", "migration_value", "session_value", "admin_value"):
        assert value not in output


def test_failure_does_not_propagate_database_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    def failed(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(["psql"], 1, b"password_in_stdout", b"secret_sql")

    monkeypatch.setattr("app.ops.bootstrap_cloud_secrets.subprocess.run", failed)
    with pytest.raises(RuntimeError) as failure:
        setup.run_command(["psql"])
    assert "password_in_stdout" not in str(failure.value)
    assert "secret_sql" not in str(failure.value)


def test_role_passwords_use_local_scram_verifiers_and_certificate_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = MagicMock()
    connection.pgconn.encrypt_password.return_value = b"SCRAM-SHA-256$synthetic-verifier"
    connector = MagicMock()
    connector.return_value.__enter__.return_value = connection
    monkeypatch.setattr(setup, "connect", connector)
    setup.set_role_passwords(
        "a" * 20, "pooler.example", "admin_value", {"jhworks_runtime": "raw_value"}
    )
    connection.pgconn.encrypt_password.assert_called_once_with(
        b"raw_value", b"jhworks_runtime", algorithm=b"scram-sha-256"
    )
    statement = connection.execute.call_args.args[0].as_string()
    assert "SCRAM-SHA-256$synthetic-verifier" in statement and "raw_value" not in statement
    assert connector.call_args.kwargs["sslmode"] == "verify-full"
    assert connector.call_args.kwargs["prepare_threshold"] is None
    assert connector.call_args.kwargs["sslrootcert"] == setup.DEPLOYMENT_CA_PATH

import json
from unittest.mock import MagicMock

import pytest

from app.ops import demo_credentials as setup


def argv() -> list[str]:
    return [
        "demo-credentials", "--project=synthetic-project", "--project-ref=" + "a" * 20,
        "--pooler-host=aws-0-ap-northeast-2.pooler.supabase.com", "--ca-file=synthetic-ca.crt",
        "--apply",
    ]


def cli(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.setattr("sys.argv", argv())
    monkeypatch.setattr("app.ops.demo_credentials.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("app.ops.demo_credentials.sys.stderr.isatty", lambda: True)
    monkeypatch.setattr("app.ops.demo_credentials.shutil.which", lambda _: "/bin/gcloud")
    monkeypatch.setattr("app.ops.demo_credentials.Path.is_file", lambda _: True)
    prompt = MagicMock(return_value="synthetic-admin-password")
    monkeypatch.setattr("app.ops.demo_credentials.getpass.getpass", prompt)
    return prompt


def test_no_terminal_or_cloud_preflight_failure_never_prompts_for_password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt = cli(monkeypatch)
    cloud = MagicMock(side_effect=RuntimeError("synthetic-sensitive-diagnostic"))
    monkeypatch.setattr(setup, "cloud_preflight", cloud)
    monkeypatch.setattr("app.ops.demo_credentials.sys.stdin.isatty", lambda: False)
    assert setup.main() == 1
    cloud.assert_not_called()
    prompt.assert_not_called()
    monkeypatch.setattr("app.ops.demo_credentials.sys.stdin.isatty", lambda: True)
    assert setup.main() == 1
    prompt.assert_not_called()
    assert "synthetic-sensitive-diagnostic" not in capsys.readouterr().out


def test_single_hidden_prompt_without_confirmation_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt = cli(monkeypatch)
    monkeypatch.setattr(setup, "cloud_preflight", MagicMock())
    bootstrap = MagicMock()
    monkeypatch.setattr(setup, "bootstrap", bootstrap)
    assert setup.main() == 0
    prompt.assert_called_once_with("Existing Supabase postgres password (hidden): ")
    assert bootstrap.call_args.args[3] == "synthetic-admin-password"
    assert "synthetic-admin-password" not in capsys.readouterr().out


def test_existing_version_blocks_initial_setup_and_never_reads_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = MagicMock(return_value=b'[{"name":"existing/versions/1"}]')
    monkeypatch.setattr(setup, "run_command", runner)
    with pytest.raises(RuntimeError, match="empty secret"):
        setup.cloud_preflight("synthetic-project")
    runner.assert_called_once()
    assert "access" not in runner.call_args.args[0]


@pytest.mark.parametrize("bad_binding", ["wrong-member", "unconditional", "wrong-version"])
def test_unexpected_secret_access_blocks_setup(
    monkeypatch: pytest.MonkeyPatch, bad_binding: str
) -> None:
    member = "serviceAccount:jhworks-demo-runtime@synthetic-project.iam.gserviceaccount.com"
    binding = {
        "role": "roles/secretmanager.secretAccessor", "members": [member],
        "condition": {"expression": "resource.name.endsWith('/versions/1')"},
    }
    if bad_binding == "wrong-member":
        binding["members"] = ["allUsers"]
    elif bad_binding == "unconditional":
        binding.pop("condition")
    else:
        binding["condition"] = {"expression": "resource.name.endsWith('/versions/2')"}
    results = iter([b"[]", json.dumps({"bindings": [binding]}).encode()])
    monkeypatch.setattr(setup, "run_command", lambda *args, **kwargs: next(results))
    with pytest.raises(RuntimeError, match="permissions"):
        setup.cloud_preflight("synthetic-project")


def test_database_preflight_rejects_existing_tables_and_active_roles() -> None:
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = ("postgres", "jhworks_demo_migrate", 1)
    with pytest.raises(RuntimeError, match="empty demo schema"):
        setup.database_preflight(connection)
    connection.execute.return_value.fetchone.return_value = ("postgres", "jhworks_demo_migrate", 0)
    connection.execute.return_value.fetchall.return_value = [
        ("jhworks_demo_migrate", False, False, False, False, False, False, False, False),
        ("jhworks_demo_runtime", True, False, False, False, False, False, False, False),
    ]
    with pytest.raises(RuntimeError, match="NOLOGIN"):
        setup.database_preflight(connection)


@pytest.mark.parametrize("fail_second_write", [False, True])
def test_secrets_use_stdin_and_login_activates_only_after_all_versions(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], fail_second_write: bool
) -> None:
    connection = MagicMock()
    connection.pgconn.encrypt_password.return_value = b"SCRAM-SHA-256$synthetic-verifier"
    connector = MagicMock()
    connector.return_value.__enter__.return_value = connection
    monkeypatch.setattr(setup, "connect", connector)
    monkeypatch.setattr(setup, "cloud_preflight", MagicMock())
    monkeypatch.setattr(setup, "database_preflight", MagicMock())
    verified = MagicMock()
    monkeypatch.setattr(setup, "verify_credentials", verified)
    generated = iter(["runtime_" + "r" * 64, "migration_" + "m" * 64, "session_" + "s" * 64])
    monkeypatch.setattr("app.ops.demo_credentials.secrets.token_urlsafe", lambda _: next(generated))
    calls: list[tuple[list[str], bytes | None]] = []

    def run(arguments: list[str], *, payload: bytes | None = None) -> bytes:
        calls.append((arguments, payload))
        statements = [
            c.args[0].as_string() for c in connection.execute.call_args_list
            if not isinstance(c.args[0], str)
        ]
        assert not any(s.endswith(" LOGIN") for s in statements)
        if "add" in arguments:
            if fail_second_write and len([c for c in calls if "add" in c[0]]) == 2:
                raise RuntimeError("synthetic-sensitive-gcp-diagnostic")
            return b"projects/synthetic/secrets/demo/versions/1"
        return b"ENABLED"

    monkeypatch.setattr(setup, "run_command", run)
    if fail_second_write:
        with pytest.raises(RuntimeError):
            setup.bootstrap("synthetic-project", "a" * 20, "pooler.example", "admin_value", "ca")
        verified.assert_not_called()
        assert connector.return_value.__exit__.call_args.args[0] is RuntimeError
    else:
        setup.bootstrap("synthetic-project", "a" * 20, "pooler.example", "admin_value", "ca")
        verified.assert_called_once()
        assert connector.return_value.__exit__.call_args.args == (None, None, None)
    statements = [
        c.args[0].as_string() for c in connection.execute.call_args_list
        if not isinstance(c.args[0], str)
    ]
    assert sum(s.endswith(" LOGIN") for s in statements) == (0 if fail_second_write else 2)
    secret_calls = [c for c in calls if "add" in c[0]]
    assert all("--data-file=-" in args and payload for args, payload in secret_calls)
    output = capsys.readouterr().out + repr([c[0] for c in calls]) + repr(statements)
    for sensitive in ["admin_value", "runtime_" + "r" * 64, "migration_" + "m" * 64,
                      "session_" + "s" * 64]:
        assert sensitive not in output
    assert connector.call_args.kwargs["sslmode"] == "verify-full"
    assert connector.call_args.kwargs["prepare_threshold"] is None

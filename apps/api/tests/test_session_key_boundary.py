import json
import subprocess
import sys
from typing import Any

import pytest

from app.ops import session_key_boundary as probe


def run_fixture(arguments: list[str]) -> str:
    service = arguments[3]
    if arguments[2] == "get-iam-policy":
        return json.dumps({"bindings": []})
    account, secret = probe.TARGETS[service]
    return json.dumps({
        "metadata": {"annotations": {}},
        "spec": {"template": {"metadata": {"name": "ready"}, "spec": {
            "serviceAccountName": f"{account}@{probe.PROJECT}.iam.gserviceaccount.com",
            "containers": [{"name": "api", "env": [
                {"name": "JHWORKS_AI_ENABLED", "value": "false"},
                {"name": "JHWORKS_JWT_SECRET", "valueFrom": {
                    "secretKeyRef": {"name": secret, "key": "1"}}},
            ]}],
        }}},
        "status": {"latestReadyRevisionName": "ready",
                   "traffic": [{"revisionName": "ready", "percent": 100}]},
    })


def test_inspect_checks_both_services_without_secret_payloads() -> None:
    calls = []

    def run(arguments: list[str]) -> str:
        calls.append(arguments)
        return run_fixture(arguments)

    assert probe.inspect_references(run) == [v[1] for v in probe.TARGETS.values()]
    assert len(calls) == 4 and all(c[:2] == ["run", "services"] for c in calls)


@pytest.mark.parametrize(
    "change", ["identity", "reference", "public", "traffic", "ai", "algorithm"],
)
def test_cli_refuses_drift_before_any_secret_read(
    change: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def run(arguments: list[str]) -> str:
        assert arguments[:2] == ["run", "services"]
        state = json.loads(run_fixture(arguments))
        if arguments[2] == "get-iam-policy":
            if change == "public":
                state["bindings"] = [{"members": ["allUsers"]}]
        else:
            spec = state["spec"]["template"]["spec"]
            if change == "identity":
                spec["serviceAccountName"] = "unexpected"
            elif change == "reference":
                spec["containers"][0]["env"][1]["valueFrom"]["secretKeyRef"]["key"] = "latest"
            elif change == "traffic":
                state["status"]["traffic"][0]["revisionName"] = "old"
            elif change == "ai":
                spec["containers"][0]["env"][0]["value"] = "true"
            elif change == "algorithm":
                spec["containers"][0]["env"].append({"name": "JHWORKS_JWT_ALGORITHM",
                                                    "value": "HS512"})
        return json.dumps(state)

    monkeypatch.setattr(probe, "command", run)
    monkeypatch.setattr(sys, "argv", ["probe", "--verify-keys"])
    assert probe.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["secretPayloadsRead"] == 0 and report["stage"] == "service_references"


@pytest.mark.parametrize("keys", [["x" * 32, "x" * 32], ["short", "y" * 32], []])
def test_same_or_weak_keys_are_rejected(keys: list[str]) -> None:
    with pytest.raises(ValueError):
        probe.verify_keys(keys)


@pytest.mark.parametrize("verify", [False, True])
def test_opt_in_and_success_report_never_expose_keys_or_tokens(
    verify: bool, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    secrets = ["synthetic-private-" + "a" * 32, "synthetic-demo-" + "b" * 32]
    reads = []

    def run(arguments: list[str]) -> str:
        if arguments[0] == "secrets":
            reads.append(arguments)
            return secrets[len(reads) - 1]
        return run_fixture(arguments)

    monkeypatch.setattr(probe, "command", run)
    monkeypatch.setattr(sys, "argv", ["probe"] + (["--verify-keys"] if verify else []))
    assert probe.main() == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["secretPayloadsRead"] == (2 if verify else 0)
    assert report["keysVerified"] is verify
    assert all(secret not in output for secret in secrets)
    assert "eyJ" not in output and report["httpRequests"] == 0 and report["writes"] == 0
    if verify:
        assert report["crossSignaturesRejected"] == 2 and report["ownSignaturesAccepted"] == 2


def test_secret_failure_does_not_leak_subprocess_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("synthetic secret or provider text")

    monkeypatch.setattr(probe, "command", fail)
    monkeypatch.setattr(sys, "argv", ["probe", "--verify-keys"])
    assert probe.main() == 1
    assert "synthetic secret" not in capsys.readouterr().out


def test_secret_bytes_are_not_normalized_or_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    stored = b"synthetic-key-with-exact-newlines-1234\r\n"

    def run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        assert "text" not in kwargs and "encoding" not in kwargs
        return subprocess.CompletedProcess(arguments, 0, stored, b"")

    monkeypatch.setattr("app.ops.session_key_boundary.subprocess.run", run)
    assert probe.command(["secrets"]) == stored.decode("utf-8")


def test_second_secret_failure_reports_partial_access_without_key_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    count = 0

    def run(arguments: list[str]) -> str:
        nonlocal count
        if arguments[0] == "secrets":
            count += 1
            if count == 2:
                raise RuntimeError("synthetic second secret failure")
            return "synthetic-first-secret-" + "x" * 32
        return run_fixture(arguments)

    monkeypatch.setattr(probe, "command", run)
    monkeypatch.setattr(sys, "argv", ["probe", "--verify-keys"])
    assert probe.main() == 1
    output = capsys.readouterr().out
    assert "synthetic" not in output
    assert json.loads(output)["secretPayloadsRead"] == 1

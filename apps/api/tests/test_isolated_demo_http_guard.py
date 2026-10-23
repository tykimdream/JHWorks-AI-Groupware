import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


@pytest.mark.parametrize("change", ["revision", "account", "secret", "public"])
def test_operator_smoke_refuses_unsafe_target_before_identity_token_or_http(
    change: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = Path(__file__).resolve().parents[3] / "deploy/cloud-run/verify-isolated-demo.py"
    spec = importlib.util.spec_from_file_location("isolated_demo_http_guard", path)
    assert spec is not None and spec.loader is not None
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    state: dict[str, Any] = {
        "metadata": {
            "annotations": {
                "run.googleapis.com/invoker-iam-disabled": "false",
                "run.googleapis.com/maxScale": "1",
            }
        },
        "spec": {
            "template": {
                "metadata": {"name": script.REVISION},
                "spec": {
                    "serviceAccountName": (
                        f"jhworks-demo-runtime@{script.PROJECT}.iam.gserviceaccount.com"
                    ),
                    "containers": [
                        {
                            "name": "api",
                            "env": [
                                {"name": "JHWORKS_AI_ENABLED", "value": "false"},
                                {
                                    "name": "JHWORKS_DATABASE_URL",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": "jhworks-demo-runtime-database",
                                            "key": "1",
                                        }
                                    },
                                },
                                {
                                    "name": "JHWORKS_JWT_SECRET",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": "jhworks-demo-session-secret",
                                            "key": "1",
                                        }
                                    },
                                },
                            ],
                        }
                    ],
                },
            }
        },
        "status": {"traffic": [{"revisionName": script.REVISION, "percent": 100}]},
    }
    policy: dict[str, Any] = {"bindings": []}
    if change == "revision":
        state["spec"]["template"]["metadata"]["name"] = "unexpected-revision"
    elif change == "account":
        state["spec"]["template"]["spec"]["serviceAccountName"] = "shared-runtime"
    elif change == "secret":
        state["spec"]["template"]["spec"]["containers"][0]["env"][1]["valueFrom"]["secretKeyRef"][
            "name"
        ] = "jhworks-runtime-database"
    else:
        policy = {"bindings": [{"role": "roles/run.invoker", "members": ["allUsers"]}]}
    commands: list[list[str]] = []
    http_calls: list[str] = []

    def run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(arguments)
        assert arguments[:3] == ["gcloud", "run", "services"]
        value = policy if "get-iam-policy" in arguments else state
        return subprocess.CompletedProcess(arguments, 0, json.dumps(value), "")

    def reject_http(*args: Any, **kwargs: Any) -> None:
        http_calls.append("unexpected_http")
        raise AssertionError("No HTTP client is allowed before the target guards pass")

    output = tmp_path / "report.json"
    monkeypatch.setattr(script.subprocess, "run", run)
    monkeypatch.setattr(script.httpx, "Client", reject_http)
    monkeypatch.setattr(sys, "argv", [str(path), "--apply", "--output", str(output)])
    assert script.main() == 1
    report = json.loads(output.read_text())
    assert report["stage"] == "private_service_guard"
    assert report["syntheticCreated"] == {"visits": 0, "approvals": 0, "feedback": 0}
    assert report["checks"] == [] and http_calls == []
    assert all("print-identity-token" not in command for command in commands)

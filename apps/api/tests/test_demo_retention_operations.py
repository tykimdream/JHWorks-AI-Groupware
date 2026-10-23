import base64
import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.ops import demo_retention_operations as ops

IMAGE = ("asia-northeast3-docker.pkg.dev/jhworks-staging-tykimdream/jhworks/api@sha256:"
         + "a" * 64)
CHANNEL = "projects/jhworks-staging-tykimdream/notificationChannels/12345"


def test_scheduler_cannot_override_job_or_read_credentials() -> None:
    bundle = ops.operations_bundle(IMAGE, [CHANNEL])
    scheduler = bundle["scheduler.json"]
    assert "state" not in scheduler  # Output-only: do not assume paused creation.
    assert scheduler["schedule"] == "17 * * * *" and scheduler["timeZone"] == "Etc/UTC"
    assert scheduler["retryConfig"] == {"retryCount": 0, "maxRetryDuration": "0s"}
    assert scheduler["attemptDeadline"] == "30s"
    target = scheduler["httpTarget"]
    assert target["httpMethod"] == "POST" and "oidcToken" not in target
    assert json.loads(base64.b64decode(target["body"])) == {}  # No runWithOverrides.
    assert target["uri"] == (
        "https://run.googleapis.com/v2/projects/jhworks-staging-tykimdream/"
        "locations/asia-northeast3/jobs/jhworks-demo-retention-maintenance:run"
    )
    assert target["oauthToken"]["serviceAccountEmail"] == ops.CALLER
    assert bundle["invoker-binding.json"] == {
        "resource": "projects/jhworks-staging-tykimdream/locations/asia-northeast3/jobs/"
                    "jhworks-demo-retention-maintenance",
        "role": "roles/run.invoker", "member": "serviceAccount:" + ops.CALLER,
    }


def test_dryrun_first_and_separate_apply_artifact_preserve_isolation() -> None:
    bundle = ops.operations_bundle(IMAGE, [])
    dry, apply = bundle["job-dryrun.json"], bundle["job-apply.json"]
    assert dry["metadata"]["name"] == apply["metadata"]["name"] == ops.JOB
    assert ops.JOB != "jhworks-demo-maintenance"  # Existing manual job is preserved.
    spec = dry["spec"]["template"]["spec"]
    assert spec["taskCount"] == spec["parallelism"] == 1
    task = spec["template"]["spec"]
    assert task["maxRetries"] == 0 and task["timeoutSeconds"] == "120"
    assert task["serviceAccountName"] == (
        "jhworks-demo-runtime@jhworks-staging-tykimdream.iam.gserviceaccount.com"
    )
    container = task["containers"][0]
    assert "--apply" not in container["args"]
    assert container["args"] == ["-m", "app.ops.demo_maintenance", "--batch-size", "5"]
    env = {e["name"]: e for e in container["env"]}
    assert env["JHWORKS_AI_ENABLED"]["value"] == "false"
    assert env["JHWORKS_PUBLIC_DEMO_ENABLED"]["value"] == "true"
    assert [e["valueFrom"]["secretKeyRef"] for e in env.values() if "valueFrom" in e] == [
        {"name": "jhworks-demo-runtime-database", "key": "1"},
        {"name": "jhworks-demo-session-secret", "key": "1"},
    ]
    apply_container = apply["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]
    assert apply_container.pop("args") == container["args"] + ["--apply"]
    assert apply_container == {k: v for k, v in container.items() if k != "args"}
    assert bundle["rollout.json"]["notificationChannelConfigured"] is False


def test_alerts_distinguish_failure_and_missing_success_and_start_disabled() -> None:
    bundle = ops.operations_bundle(IMAGE, [CHANNEL])
    for kind in ("failed", "missing"):
        policy = bundle[kind + "-alert.json"]
        assert policy["enabled"] is False and policy["notificationChannels"] == [CHANNEL]
        condition = policy["conditions"][0]["conditionPrometheusQueryLanguage"]
        assert condition["disableMetricValidation"] is False
        assert condition["evaluationInterval"] == condition["duration"] == "60s"
        query = condition["query"]
        for boundary in ('project_id="jhworks-staging-tykimdream"', 'location="asia-northeast3"',
                         'job_name="jhworks-demo-retention-maintenance"',
                         'monitored_resource="cloud_run_job"'):
            assert boundary in query
        assert " bool " not in query  # Healthy zero-valued bool vectors would also fire.
        if kind == "missing":
            assert 'result="succeeded"' in query and "[3h]" in query
            assert "or vector(0)" in query and query.endswith("< 1")
        else:
            assert 'result!="succeeded"' in query and "[10m]" in query
            assert query.endswith("> 0")


@pytest.mark.parametrize("channels", [
    [CHANNEL, CHANNEL], [CHANNEL, CHANNEL + "1", CHANNEL + "2"],
    [CHANNEL.replace("jhworks-staging-tykimdream", "other-project")],
    ["person@example.invalid"], [CHANNEL + '\" or vector(1)'],
])
def test_invalid_channels_cannot_widen_or_inject_targets(channels: list[str]) -> None:
    with pytest.raises(ValueError):
        ops.operations_bundle(IMAGE, channels)


@pytest.mark.parametrize("image", [
    IMAGE.replace("@sha256:" + "a" * 64, ":latest"),
    IMAGE.replace("asia-northeast3", "us-central1"),
    IMAGE.replace("jhworks-staging-tykimdream", "other-project"),
])
def test_mutable_foreign_or_wrong_region_image_rejected(image: str) -> None:
    with pytest.raises(ValueError):
        ops.operations_bundle(image, [])


def test_query_target_injection_rejected() -> None:
    with pytest.raises(ValueError):
        ops.queries('jhworks-staging\"}')


def test_cli_is_offline_and_refuses_overwrite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("Bundle rendering must never access cloud, credentials or network")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    directory = tmp_path / "bundle"
    monkeypatch.setattr(sys, "argv", ["ops", "--api-image", IMAGE, "--output-dir", str(directory)])
    ops.main()
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "plan_only" and result["cloudWrites"] == 0
    assert not result["notificationChannelConfigured"]
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    assert sorted(before) == result["files"] and len(before) == 7
    with pytest.raises(FileExistsError):
        ops.main()
    assert before == {p.name: p.read_bytes() for p in directory.iterdir()}

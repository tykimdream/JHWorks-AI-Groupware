import base64
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.ops.demo_maintenance_schedule import OperationsSettings, main, operations_manifests

EXAMPLE = (
    Path(__file__).resolve().parents[3] / "deploy/cloud-run/maintenance-operations.example.json"
)


def data() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(EXAMPLE.read_text())
    return raw  # No credential values, only resource references.


def test_scheduler_cannot_override_commands_or_use_runtime_identity() -> None:
    settings = OperationsSettings.model_validate(data())
    outputs = operations_manifests(settings)
    scheduler = outputs["scheduler-create.json"]
    target = scheduler["httpTarget"]
    assert json.loads(base64.b64decode(target["body"])) == {}
    assert "oidcToken" not in target
    assert (
        target["oauthToken"]["serviceAccountEmail"] != settings.maintenance.runtime_service_account
    )
    assert target["uri"] == (
        "https://run.googleapis.com/v2/projects/replace-project/locations/asia-northeast3"
        "/jobs/jhworks-demo-maintenance:run"
    )
    assert scheduler["retryConfig"] == {"retryCount": 0, "maxRetryDuration": "0s"}
    assert "state" not in scheduler  # PAUSED is output-only, not a creation safety gate.
    binding = outputs["scheduler-invoker-binding.json"]
    assert binding["role"] == "roles/run.invoker"  # No runWithOverrides, actAs or Secret access.
    assert outputs["approval-plan.json"]["invokerBindingTarget"].endswith(
        "/jobs/jhworks-demo-maintenance"
    )


def test_alerts_remain_disabled_with_or_without_channel_and_scope_one_job() -> None:
    for channel in (None, "projects/replace-project/notificationChannels/123"):
        raw = data()
        raw["notification_channel"] = channel
        outputs = operations_manifests(OperationsSettings.model_validate(raw))
        for filename, condition_key, result in (
            ("failure-alert-disabled.json", "conditionThreshold", "failed"),
            ("missing-alert-disabled.json", "conditionAbsent", "succeeded"),
        ):
            policy = outputs[filename]
            assert policy["enabled"] is False
            assert policy["notificationChannels"] == ([channel] if channel else [])
            condition = policy["conditions"][0][condition_key]
            assert 'resource.type="cloud_run_job"' in condition["filter"]
            assert 'resource.labels.project_id="replace-project"' in condition["filter"]
            assert 'resource.labels.job_name="jhworks-demo-maintenance"' in condition["filter"]
            assert f'metric.labels.result="{result}"' in condition["filter"]
        assert outputs["missing-alert-disabled.json"]["conditions"][0]["conditionAbsent"][
            "duration"
        ] == "10800s"
        missing = outputs["missing-alert-disabled.json"]
        # A stream of zero samples is not absent. Handle both platform behaviors.
        zero_count = missing["conditions"][1]["conditionThreshold"]
        assert zero_count["comparison"] == "COMPARISON_LT" and zero_count["thresholdValue"] == 1
        assert zero_count["aggregations"][0]["alignmentPeriod"] == "10800s"
        assert zero_count["evaluationMissingData"] == "EVALUATION_MISSING_DATA_NO_OP"
        assert missing["combiner"] == "OR"
        assert int(missing["alertStrategy"]["autoClose"][:-1]) > 10800


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("job", "jhworks-staging-maintenance"),
        ("region", "us-central1"),
        ("runtime_service_account", "jhworks-runtime@replace-project.iam.gserviceaccount.com"),
        ("runtime_database", {"name": "jhworks-migration-database", "version": "1"}),
        ("jwt_secret", {"name": "jhworks-demo-session-secret", "version": "latest"}),
        ("runtime_database", {"name": "jhworks-demo-runtime-database", "version": "2"}),
    ],
)
def test_private_or_unreviewed_profile_rejected(field: str, value: Any) -> None:
    raw = data()
    raw["maintenance"][field] = value
    with pytest.raises(ValidationError):
        OperationsSettings.model_validate(raw)


@pytest.mark.parametrize(
    "channel",
    ["projects/foreign-project/notificationChannels/123", "https://foreign.test/123", "allUsers"],
)
def test_foreign_notification_destination_rejected(channel: str) -> None:
    raw = data()
    raw["notification_channel"] = channel
    with pytest.raises(ValidationError):
        OperationsSettings.model_validate(raw)


def test_unsupported_cost_or_access_overrides_are_rejected() -> None:
    for field, value in (("schedule", "* * * * *"), ("scheduler_account", "allUsers")):
        raw = deepcopy(data())
        raw[field] = value
        with pytest.raises(ValidationError):
            OperationsSettings.model_validate(raw)


def test_cli_rejects_bad_profile_before_creating_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = data()
    raw["maintenance"]["job"] = "jhworks-staging-maintenance"
    config = tmp_path / "settings.json"
    config.write_text(json.dumps(raw))
    output = tmp_path / "plan"
    monkeypatch.setattr("sys.argv", ["plan", "--settings", str(config), "--output", str(output)])
    with pytest.raises(ValidationError):
        main()
    assert not output.exists()


def test_cli_never_overwrites_an_existing_reviewed_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "plan"
    monkeypatch.setattr("sys.argv", ["plan", "--settings", str(EXAMPLE), "--output", str(output)])
    main()
    sentinel = output / "failure-alert-disabled.json"
    sentinel.write_text("previously reviewed operator plan")
    with pytest.raises(FileExistsError):
        main()
    assert sentinel.read_text() == "previously reviewed operator plan"

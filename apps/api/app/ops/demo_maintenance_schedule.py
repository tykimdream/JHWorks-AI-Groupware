"""Offline Scheduler/alert drafts. Never enables APIs, grants IAM or calls GCP."""

import argparse
import base64
import json
import re
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.ops.demo_maintenance_manifest import MaintenanceSettings


class OperationsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    maintenance: MaintenanceSettings
    notification_channel: str | None = None

    @model_validator(mode="after")
    def isolated_demo(self) -> Self:
        config = self.maintenance
        if (
            config.job != "jhworks-demo-maintenance"
            or config.region != "asia-northeast3"
            or config.runtime_service_account
            != f"jhworks-demo-runtime@{config.project_id}.iam.gserviceaccount.com"
            or config.runtime_database.name != "jhworks-demo-runtime-database"
            or config.jwt_secret.name != "jhworks-demo-session-secret"
            or config.runtime_database.version != "1"
            or config.jwt_secret.version != "1"
        ):
            raise ValueError("Use the isolated Seoul demo maintenance profile and Secret v1")
        if self.notification_channel is not None and not re.fullmatch(
            rf"projects/{re.escape(config.project_id)}/notificationChannels/[0-9]+",
            self.notification_channel,
        ):
            raise ValueError("Use an existing numeric notification channel in the same project")
        return self

    @property
    def scheduler_account(self) -> str:
        return f"jhworks-demo-scheduler@{self.maintenance.project_id}.iam.gserviceaccount.com"


def operations_manifests(settings: OperationsSettings) -> dict[str, Any]:
    config = settings.maintenance
    project = config.project_id
    resource_filter = (
        'resource.type="cloud_run_job" '
        f'AND resource.labels.project_id="{project}" '
        f'AND resource.labels.location="{config.region}" '
        f'AND resource.labels.job_name="{config.job}" '
        'AND metric.type="run.googleapis.com/job/completed_execution_count" '
    )
    aggregation = [{"alignmentPeriod": "300s", "perSeriesAligner": "ALIGN_SUM"}]

    def policy(
        display_name: str, *conditions: dict[str, Any], auto_close: str = "3600s",
    ) -> dict[str, Any]:
        return {
            "displayName": display_name,
            "enabled": False,
            "combiner": "OR",
            "notificationChannels": (
                [settings.notification_channel] if settings.notification_channel else []
            ),
            "conditions": list(conditions),
            "alertStrategy": {"autoClose": auto_close},
        }

    return {
        "scheduler-create.json": {
            "name": f"projects/{project}/locations/{config.region}/jobs/jhworks-demo-retention",
            "description": "Invoke the fixed private maintenance Job; start with dry-run only",
            "schedule": "17 * * * *",
            "timeZone": "Etc/UTC",
            "attemptDeadline": "60s",
            "retryConfig": {"retryCount": 0, "maxRetryDuration": "0s"},
            "httpTarget": {
                "uri": (
                    f"https://run.googleapis.com/v2/projects/{project}"
                    f"/locations/{config.region}/jobs/{config.job}:run"
                ),
                "httpMethod": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": base64.b64encode(b"{}").decode("ascii"),
                "oauthToken": {
                    "serviceAccountEmail": settings.scheduler_account,
                    "scope": "https://www.googleapis.com/auth/cloud-platform",
                },
            },
        },
        "scheduler-invoker-binding.json": {
            "role": "roles/run.invoker",
            "members": ["serviceAccount:" + settings.scheduler_account],
        },
        "failure-alert-disabled.json": policy(
            "JHWorks demo maintenance failed",
            {
                "displayName": "A completed execution failed",
                "conditionThreshold": {
                    "filter": resource_filter + 'AND metric.labels.result="failed"',
                    "aggregations": aggregation,
                    "comparison": "COMPARISON_GT",
                    "thresholdValue": 0,
                    "duration": "0s",
                    "trigger": {"count": 1},
                },
            },
        ),
        "missing-alert-disabled.json": policy(
            "JHWorks demo maintenance success missing",
            {
                "displayName": "No successful execution for three hours",
                "conditionAbsent": {
                    "filter": resource_filter + 'AND metric.labels.result="succeeded"',
                    "aggregations": aggregation,
                    "duration": "10800s",
                    "trigger": {"count": 1},
                },
            },
            {
                "displayName": "Successful execution count is zero across three hours",
                "conditionThreshold": {
                    "filter": resource_filter + 'AND metric.labels.result="succeeded"',
                    "aggregations": [
                        {"alignmentPeriod": "10800s", "perSeriesAligner": "ALIGN_SUM"}
                    ],
                    "comparison": "COMPARISON_LT",
                    "thresholdValue": 1,
                    "duration": "60s",
                    "evaluationMissingData": "EVALUATION_MISSING_DATA_NO_OP",
                    "trigger": {"count": 1},
                },
            },
            auto_close="86400s",
        ),
        "approval-plan.json": {
            "cloudOperationsPerformed": False,
            "schedulerAccount": settings.scheduler_account,
            "invokerBindingTarget": (
                f"projects/{project}/locations/{config.region}/jobs/{config.job}"
            ),
            "jobDefaultMustRemainDryRunDuringSetup": True,
            "schedulerCreateStateIsNotWritable": True,
            "pauseAndVerifyBeforeChangingMaintenanceMode": True,
            "notificationChannelRequiredBeforeEnablingAlerts": True,
            "nativeMetricAndDeliveryDrillsRequired": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = OperationsSettings.model_validate_json(args.settings.read_text(encoding="utf-8"))
    manifests = operations_manifests(settings)
    # Never overwrite an earlier reviewed plan. No subprocess, SDK or network use.
    args.output.mkdir(parents=True, exist_ok=False)
    for name, payload in manifests.items():
        (args.output / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "prepared", "files": list(manifests), "cloudOperations": 0}))


if __name__ == "__main__":
    main()

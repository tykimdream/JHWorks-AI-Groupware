"""Render a fixed staging retention rollout bundle; no cloud access or activation."""

import argparse
import base64
import json
import re
from pathlib import Path
from typing import Any

from app.ops.demo_maintenance_manifest import MaintenanceSettings, maintenance_manifest

PROJECT = "jhworks-staging-tykimdream"
REGION = "asia-northeast3"
JOB = "jhworks-demo-retention-maintenance"
SCHEDULER = "jhworks-demo-retention-hourly"
CALLER = f"jhworks-demo-scheduler@{PROJECT}.iam.gserviceaccount.com"
METRIC = "run.googleapis.com/job/completed_execution_count"


def selector(job: str = JOB, *, success: bool) -> str:
    # This is also used for read-only controls against the existing dry-run job.
    if job not in {JOB, "jhworks-demo-maintenance"}:
        raise ValueError("Unexpected job")
    result = 'result="succeeded"' if success else 'result!="succeeded"'
    return (
        f'{{"{METRIC}",monitored_resource="cloud_run_job",project_id="{PROJECT}",'
        f'location="{REGION}",job_name="{job}",{result}}}'
    )


def queries(job: str = JOB) -> dict[str, str]:
    return {
        "failed": f"sum(sum_over_time({selector(job, success=False)}[10m])) > 0",
        # A comparison without `bool` returns a vector only when unhealthy.
        # Empty data becomes zero, but a stream of zero points also stays unhealthy.
        "missing": f"(sum(sum_over_time({selector(job, success=True)}[3h])) or vector(0)) < 1",
    }


def operations_bundle(image: str, channels: list[str]) -> dict[str, dict[str, Any]]:
    if len(channels) != len(set(channels)) or len(channels) > 2:
        raise ValueError("Use at most two distinct notification channels")
    for channel in channels:
        if not re.fullmatch(rf"projects/{PROJECT}/notificationChannels/[0-9]+", channel):
            raise ValueError("Use existing notification channel resource names in this project")
    settings = MaintenanceSettings(
        project_id=PROJECT, region=REGION, job=JOB,
        runtime_service_account=f"jhworks-demo-runtime@{PROJECT}.iam.gserviceaccount.com",
        runtime_database={"name": "jhworks-demo-runtime-database", "version": "1"},
        jwt_secret={"name": "jhworks-demo-session-secret", "version": "1"},
    )
    bundle: dict[str, dict[str, Any]] = {
        "job-dryrun.json": maintenance_manifest(settings, image),
        "job-apply.json": maintenance_manifest(settings, image, apply=True),
        "scheduler.json": {
            "name": f"projects/{PROJECT}/locations/{REGION}/jobs/{SCHEDULER}",
            "description": "Hourly isolated demo retention; create only against dry-run job",
            "schedule": "17 * * * *", "timeZone": "Etc/UTC", "attemptDeadline": "30s",
            "retryConfig": {"retryCount": 0, "maxRetryDuration": "0s"},
            "httpTarget": {
                "uri": f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}"
                       f"/jobs/{JOB}:run",
                "httpMethod": "POST", "headers": {"Content-Type": "application/json"},
                "body": base64.b64encode(b"{}").decode(),
                "oauthToken": {"serviceAccountEmail": CALLER,
                               "scope": "https://www.googleapis.com/auth/cloud-platform"},
            },
        },
        # This is a single additive binding, never a replacement IAM policy.
        "invoker-binding.json": {
            "resource": f"projects/{PROJECT}/locations/{REGION}/jobs/{JOB}",
            "role": "roles/run.invoker", "member": "serviceAccount:" + CALLER,
        },
    }
    for kind, query in queries().items():
        title = "failed execution" if kind == "failed" else "no successful completion for 3 hours"
        bundle[kind + "-alert.json"] = {
            "displayName": "JHWorks demo retention: " + title,
            "enabled": False, "combiner": "OR", "severity": "ERROR",
            "notificationChannels": channels,
            "userLabels": {"application": "jhworks", "purpose": "demo-retention"},
            "documentation": {
                "mimeType": "text/markdown",
                "content": "Pause the scheduler; inspect execution completion and sanitized "
                           "app JSON. Scheduler HTTP success is only submission. Do not retry "
                           "an unknown execution or restore the source database automatically. "
                           "Runbook: docs/engineering/demo-retention-operations.md",
            },
            "conditions": [{
                "displayName": title,
                "conditionPrometheusQueryLanguage": {
                    "query": query, "duration": "60s", "evaluationInterval": "60s",
                    "ruleGroup": "jhworks-demo-retention", "alertRule": kind,
                    "disableMetricValidation": False,
                },
            }],
            "alertStrategy": {"notificationPrompts": ["OPENED", "CLOSED"]},
        }
    bundle["rollout.json"] = {
        "status": "plan_only", "cloudWrites": 0, "notificationChannelConfigured": bool(channels),
        "newServiceAccount": CALLER, "apiToEnable": "cloudscheduler.googleapis.com",
        "requiresApproval": ["new resources and job-scoped IAM", "recurring compute charges",
                             "notification destination and delivery tests", "automatic deletion"],
        "gates": [
            "Check image provenance, current targets, names, channel verification and backup",
            "Create job from job-dryrun.json before scheduler; alerts remain disabled",
            "Create scheduler then pause and read back state; it can run before pause",
            "Enable and test both alerts; inspect execution AND app JSON AND receipt",
            "Keep paused for real 3-hour missing-success test; no lifetime success needed",
            "Approve current cleanup scope, apply job-apply.json and verify first apply success",
            "Resume only after all gates; verify a natural scheduled apply completion",
        ],
    }
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-image", required=True)
    parser.add_argument("--notification-channel", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    bundle = operations_bundle(args.api_image, args.notification_channel)
    # A fresh directory prevents accidentally overwriting a reviewed rollout.
    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, payload in bundle.items():
        (args.output_dir / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "plan_only", "files": sorted(bundle), "cloudWrites": 0,
                      "notificationChannelConfigured": bool(args.notification_channel)}))


if __name__ == "__main__":
    main()

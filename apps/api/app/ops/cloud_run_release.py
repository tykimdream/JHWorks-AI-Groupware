"""Release an IAM-protected staging service. No resource provisioning or public IAM grants."""

import argparse
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError

from app.ops.cloud_run import ReleaseSettings, migration_manifest, service_manifest
from app.ops.deployment_smoke import run_smoke

CommandRunner = Callable[[list[str]], str]
SmokeRunner = Callable[[str, str], dict[str, Any]]


class ReleaseFailure(RuntimeError):
    def __init__(self, record: dict[str, Any]) -> None:
        super().__init__("Cloud Run release failed; see sanitized release record")
        self.record = record


def run_command(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
    return result.stdout


def authenticated_smoke(url: str, token: str) -> dict[str, Any]:
    previous = os.environ.get("JHWORKS_SMOKE_IDENTITY_TOKEN")
    os.environ["JHWORKS_SMOKE_IDENTITY_TOKEN"] = token
    try:
        return run_smoke(
            api_url=f"{url}/api/v1",
            web_url=url,
            timeout_seconds=10,
            attempts=12,
            retry_interval_seconds=5,
        )
    finally:
        if previous is None:
            os.environ.pop("JHWORKS_SMOKE_IDENTITY_TOKEN", None)
        else:
            os.environ["JHWORKS_SMOKE_IDENTITY_TOKEN"] = previous


def release(
    settings: ReleaseSettings,
    api_image: str,
    web_image: str,
    commit: str,
    backup_reference: str,
    *,
    bootstrap: bool = False,
    runner: CommandRunner = run_command,
    smoke: SmokeRunner = authenticated_smoke,
) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("commit must be a full SHA")
    if not backup_reference.strip():
        raise ValueError(
            "a verified backup reference or explicit fresh-DB bootstrap reference is required"
        )
    revision = f"{settings.service}-{commit[:12]}"
    service = service_manifest(settings, api_image, web_image, revision)
    migration = migration_manifest(settings, api_image)
    common = ["--project", settings.project_id, "--region", settings.region, "--quiet"]
    previous: dict[str, Any] | None = None
    try:
        previous = json.loads(
            runner(
                [
                    "gcloud",
                    "run",
                    "services",
                    "describe",
                    settings.service,
                    *common,
                    "--format=json",
                ]
            )
        )
    except subprocess.CalledProcessError as exc:
        if not bootstrap or "NOT_FOUND" not in (exc.stderr or ""):
            raise
    if previous is not None:
        policy = json.loads(
            runner(
                [
                    "gcloud",
                    "run",
                    "services",
                    "get-iam-policy",
                    settings.service,
                    *common,
                    "--format=json",
                ]
            )
        )
        if any(
            member in {"allUsers", "allAuthenticatedUsers"}
            for binding in policy.get("bindings", [])
            for member in binding.get("members", [])
        ):
            raise ValueError("this staging release refuses a public IAM policy")
        annotations = previous.get("metadata", {}).get("annotations", {})
        if annotations.get("run.googleapis.com/invoker-iam-disabled") == "true":
            raise ValueError("this staging release requires the invoker IAM check")
        previous_traffic = [
            {"revisionName": item["revisionName"], "percent": item["percent"]}
            for item in previous.get("status", {}).get("traffic", [])
            if item.get("percent", 0) > 0
        ]
        if not previous_traffic:
            raise ValueError("cannot deploy without a recoverable previous traffic split")
        service["spec"]["traffic"] = previous_traffic
    else:
        previous_traffic = []
    record: dict[str, Any] = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "commit": commit,
        "revision": revision,
        "apiImage": api_image,
        "webImage": web_image,
        "backupReference": backup_reference,
        "previousTraffic": previous_traffic,
        "status": "preparing",
    }
    with tempfile.TemporaryDirectory(prefix="jhworks-release-") as directory:
        paths: dict[str, Path] = {}
        for name, manifest in (("migration", migration), ("service", service)):
            path = Path(directory) / f"{name}.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            paths[name] = path
        # A failed migration never reaches services replace or traffic mutation.
        try:
            runner(["gcloud", "run", "jobs", "replace", str(paths["migration"]), *common])
            runner(
                [
                    "gcloud",
                    "run",
                    "jobs",
                    "execute",
                    f"{settings.service}-migrate",
                    *common,
                    "--wait",
                ]
            )
        except subprocess.CalledProcessError as exc:
            record.update(status="failed", stage="migration", errorType=type(exc).__name__)
            raise ReleaseFailure(record) from None
        try:
            runner(["gcloud", "run", "services", "replace", str(paths["service"]), *common])
            runner(
                [
                    "gcloud",
                    "run",
                    "services",
                    "update-traffic",
                    settings.service,
                    *common,
                    "--to-revisions",
                    f"{revision}=100",
                ]
            )
            current = json.loads(
                runner(
                    [
                        "gcloud",
                        "run",
                        "services",
                        "describe",
                        settings.service,
                        *common,
                        "--format=json",
                    ]
                )
            )
            if current["status"]["url"].rstrip("/") != settings.frontend_origin:
                raise ValueError("deployed service URL differs from the configured frontend origin")
            token = runner(
                [
                    "gcloud",
                    "auth",
                    "print-identity-token",
                    "--audiences",
                    settings.frontend_origin,
                ]
            ).strip()
            report = smoke(settings.frontend_origin, token)
            record["smoke"] = report
            if report["status"] != "passed":
                raise RuntimeError("deployment smoke failed")
        except (
            subprocess.CalledProcessError,
            RuntimeError,
            ValueError,
            KeyError,
            OSError,
            URLError,
        ) as exc:
            record.update(status="failed", stage="application", errorType=type(exc).__name__)
            if previous_traffic:
                split = ",".join(
                    f"{item['revisionName']}={item['percent']}" for item in previous_traffic
                )
                try:
                    runner(
                        [
                            "gcloud",
                            "run",
                            "services",
                            "update-traffic",
                            settings.service,
                            *common,
                            "--to-revisions",
                            split,
                        ]
                    )
                    record["rollbackTraffic"] = "restored"
                    rollback_token = runner(
                        [
                            "gcloud",
                            "auth",
                            "print-identity-token",
                            "--audiences",
                            settings.frontend_origin,
                        ]
                    ).strip()
                    record["rollbackSmoke"] = smoke(settings.frontend_origin, rollback_token)
                except (
                    subprocess.CalledProcessError,
                    OSError,
                    RuntimeError,
                    ValueError,
                ) as recovery:
                    record["rollbackErrorType"] = type(recovery).__name__
            else:
                record["rollbackTraffic"] = "no_previous_revision"
            # First deploy remains private; never delete resources or downgrade DB.
            raise ReleaseFailure(record) from None
    record["status"] = "passed"
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--api-image", required=True)
    parser.add_argument("--web-image", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--backup-reference", required=True)
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = ReleaseSettings.model_validate_json(args.settings.read_text(encoding="utf-8"))
    try:
        report = release(
            settings,
            args.api_image,
            args.web_image,
            args.commit,
            args.backup_reference,
            bootstrap=args.bootstrap,
        )
    except ReleaseFailure as exc:
        report = exc.record
    except (subprocess.CalledProcessError, RuntimeError, ValueError, KeyError, OSError) as exc:
        # gcloud stdout/stderr can contain account and configuration details.
        report = {"status": "failed", "errorType": type(exc).__name__, "commit": args.commit}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

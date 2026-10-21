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
    identity_token: str | None = None,
    runner: CommandRunner = run_command,
    smoke: SmokeRunner = authenticated_smoke,
) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("commit must be a full SHA")
    if not backup_reference.strip():
        raise ValueError(
            "a verified backup reference or explicit fresh-DB bootstrap reference is required"
        )
    if identity_token is not None and not identity_token.strip():
        raise ValueError("an explicitly supplied identity token must not be empty")
    revision = f"{settings.service}-{commit[:12]}"
    service = service_manifest(settings, api_image, web_image, revision)
    migration = migration_manifest(settings, api_image)
    common = ["--project", settings.project_id, "--region", settings.region, "--quiet"]
    previous: dict[str, Any] | None = None
    # gcloud describe renders a 404 as "Cannot find service", not a stable API code.
    # Successful structured discovery distinguishes absence from IAM/network failures.
    services = json.loads(
        runner(["gcloud", "run", "services", "list", *common, "--format=json"])
    )
    if not isinstance(services, list) or any(
        not isinstance(item, dict)
        or not isinstance(item.get("metadata"), dict)
        or not isinstance(item["metadata"].get("name"), str)
        for item in services
    ):
        raise ValueError("invalid Cloud Run service discovery response")
    exists = any(item["metadata"]["name"] == settings.service for item in services)
    if exists:
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
    elif not bootstrap:
        raise ValueError("service does not exist; an explicit bootstrap is required")
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
        operation = "migration_replace"
        try:
            runner(["gcloud", "run", "jobs", "replace", str(paths["migration"]), *common])
            operation = "migration_execute"
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
            record.update(
                status="failed", stage="migration", errorType=type(exc).__name__,
                errorOperation=operation,
            )
            raise ReleaseFailure(record) from None
        try:
            operation = "service_replace"
            runner(["gcloud", "run", "services", "replace", str(paths["service"]), *common])
            operation = "traffic_promote"
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
            operation = "service_describe"
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
            operation = "origin_validate"
            if current["status"]["url"].rstrip("/") != settings.frontend_origin:
                # Cloud Run can report the hash URL in status.url while advertising
                # the configured deterministic URL as another URL of this same service.
                advertised_urls = json.loads(
                    current.get("metadata", {})
                    .get("annotations", {})
                    .get("run.googleapis.com/urls", "[]")
                )
                if (
                    not isinstance(advertised_urls, list)
                    or not all(isinstance(url, str) for url in advertised_urls)
                    or settings.frontend_origin not in advertised_urls
                ):
                    raise ValueError(
                        "configured frontend origin is not a URL of the deployed service"
                    )
            operation = "identity_token"
            token = identity_token or runner(
                [
                    "gcloud",
                    "auth",
                    "print-identity-token",
                    "--audiences",
                    settings.frontend_origin,
                ]
            ).strip()
            operation = "application_smoke"
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
            record.update(
                status="failed", stage="application", errorType=type(exc).__name__,
                errorOperation=operation,
            )
            if previous_traffic:
                split = ",".join(
                    f"{item['revisionName']}={item['percent']}" for item in previous_traffic
                )
                recovery_operation = "traffic_restore"
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
                    recovery_operation = "identity_token"
                    rollback_token = identity_token or runner(
                        [
                            "gcloud",
                            "auth",
                            "print-identity-token",
                            "--audiences",
                            settings.frontend_origin,
                        ]
                    ).strip()
                    recovery_operation = "rollback_smoke"
                    record["rollbackSmoke"] = smoke(settings.frontend_origin, rollback_token)
                except (
                    subprocess.CalledProcessError,
                    OSError,
                    RuntimeError,
                    ValueError,
                ) as recovery:
                    record["rollbackErrorType"] = type(recovery).__name__
                    record["rollbackErrorOperation"] = recovery_operation
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
        identity_token = os.environ.get("JHWORKS_RELEASE_IDENTITY_TOKEN")
        if os.environ.get("GITHUB_ACTIONS") == "true" and not identity_token:
            raise ValueError("GitHub releases require an ID token from the auth action")
        report = release(
            settings,
            args.api_image,
            args.web_image,
            args.commit,
            args.backup_reference,
            bootstrap=args.bootstrap,
            identity_token=identity_token,
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

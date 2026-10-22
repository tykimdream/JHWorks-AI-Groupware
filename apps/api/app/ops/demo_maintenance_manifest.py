"""Render an offline, private Cloud Run Job. Never creates cloud resources."""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ops.cloud_run import SecretVersion, validate_image


class MaintenanceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(pattern=r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
    region: str = Field(pattern=r"^[a-z]+-[a-z]+[0-9]+$")
    job: str = Field(pattern=r"^[a-z][a-z0-9-]{0,37}-maintenance$")
    runtime_service_account: str
    runtime_database: SecretVersion
    jwt_secret: SecretVersion

    @model_validator(mode="after")
    def boundaries(self) -> Self:
        if not re.fullmatch(
            rf"[a-z][a-z0-9-]{{4,28}}@{re.escape(self.project_id)}\.iam\.gserviceaccount\.com",
            self.runtime_service_account,
        ):
            raise ValueError("Use a dedicated runtime account in the same project")
        if self.runtime_database.name == self.jwt_secret.name:
            raise ValueError("Database and session secrets must be separate")
        return self


def maintenance_manifest(
    settings: MaintenanceSettings, image: str, *, apply: bool = False
) -> dict[str, Any]:
    validate_image(image, settings.project_id)
    if not image.startswith(f"{settings.region}-docker.pkg.dev/"):
        raise ValueError("Image must be in the configured region")
    return {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Job",
        "metadata": {"name": settings.job},
        "spec": {
            "template": {
                "spec": {
                    "taskCount": 1,
                    "parallelism": 1,
                    "template": {
                        "spec": {
                            "serviceAccountName": settings.runtime_service_account,
                            "maxRetries": 0,
                            "timeoutSeconds": "120",
                            "containers": [
                                {
                                    "image": image,
                                    "command": ["python"],
                                    "args": ["-m", "app.ops.demo_maintenance", "--batch-size", "5"]
                                    + (["--apply"] if apply else []),
                                    "resources": {"limits": {"cpu": "1", "memory": "512Mi"}},
                                    "env": [
                                        {"name": "JHWORKS_ENVIRONMENT", "value": "production"},
                                        {"name": "JHWORKS_COOKIE_SECURE", "value": "true"},
                                        {
                                            "name": "JHWORKS_FRONTEND_ORIGIN",
                                            "value": "https://maintenance.invalid",
                                        },
                                        {"name": "JHWORKS_PUBLIC_DEMO_ENABLED", "value": "true"},
                                        {"name": "JHWORKS_AI_ENABLED", "value": "false"},
                                        {"name": "JHWORKS_DATABASE_POOL_MODE", "value": "null"},
                                        {
                                            "name": "JHWORKS_DATABASE_DISABLE_PREPARED_STATEMENTS",
                                            "value": "true",
                                        },
                                        {"name": "JHWORKS_LOG_FORMAT", "value": "json"},
                                        settings.runtime_database.environment(
                                            "JHWORKS_DATABASE_URL"
                                        ),
                                        settings.jwt_secret.environment("JHWORKS_JWT_SECRET"),
                                    ],
                                }
                            ],
                        }
                    },
                }
            }
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--api-image", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = MaintenanceSettings.model_validate_json(args.settings.read_text(encoding="utf-8"))
    manifest = maintenance_manifest(settings, args.api_image, apply=args.apply)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

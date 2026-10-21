"""Generate Cloud Run resources without credentials or network access."""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

IMAGE_PATTERN = re.compile(r"^[a-z0-9.-]+-docker\.pkg\.dev/[a-z0-9/_-]+@sha256:[a-f0-9]{64}$")


class SecretVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,255}$")
    version: str = Field(pattern=r"^[1-9][0-9]*$")

    def environment(self, variable: str) -> dict[str, Any]:
        return {
            "name": variable,
            "valueFrom": {
                "secretKeyRef": {"name": self.name, "key": self.version},
            },
        }


class ReleaseSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(pattern=r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
    region: str = Field(pattern=r"^[a-z]+-[a-z]+[0-9]+$")
    service: str = Field(pattern=r"^[a-z][a-z0-9-]{0,38}[a-z0-9]$")
    frontend_origin: str
    runtime_service_account: str
    migration_service_account: str
    runtime_database: SecretVersion
    migration_database: SecretVersion
    jwt_secret: SecretVersion
    max_instances: int = Field(default=2, ge=1, le=3)
    concurrency: int = Field(default=8, ge=1, le=16)

    @model_validator(mode="after")
    def validate_boundaries(self) -> Self:
        origin = urlsplit(self.frontend_origin)
        if (
            origin.scheme != "https"
            or not origin.hostname
            or origin.username
            or origin.password
            or origin.path
            or origin.query
            or origin.fragment
            or any(character.isspace() for character in self.frontend_origin)
        ):
            raise ValueError(
                "frontend_origin must be an HTTPS origin without credentials or a path"
            )
        for account in (self.runtime_service_account, self.migration_service_account):
            if not re.fullmatch(
                rf"[a-z][a-z0-9-]{{4,28}}@{re.escape(self.project_id)}\.iam\.gserviceaccount\.com",
                account,
            ):
                raise ValueError(
                    "service accounts must be dedicated accounts in the release project"
                )
        if self.runtime_service_account == self.migration_service_account:
            raise ValueError("migration and runtime service accounts must be separate")
        if self.runtime_database.name == self.migration_database.name:
            raise ValueError("runtime and migration database secrets must be separate")
        return self


def validate_image(image: str, project_id: str) -> None:
    if not IMAGE_PATTERN.fullmatch(image) or image.split("/", 2)[1] != project_id:
        raise ValueError(
            "images must be immutable Artifact Registry digests in the release project"
        )


def api_environment(settings: ReleaseSettings, *, migration: bool = False) -> list[dict[str, Any]]:
    database = settings.migration_database if migration else settings.runtime_database
    return [
        {"name": "JHWORKS_ENVIRONMENT", "value": "production"},
        {"name": "JHWORKS_FRONTEND_ORIGIN", "value": settings.frontend_origin},
        {"name": "JHWORKS_COOKIE_SECURE", "value": "true"},
        {"name": "JHWORKS_COOKIE_SAMESITE", "value": "lax"},
        {"name": "JHWORKS_AI_ENABLED", "value": "false"},
        {"name": "JHWORKS_DATABASE_POOL_MODE", "value": "null"},
        {"name": "JHWORKS_DATABASE_DISABLE_PREPARED_STATEMENTS", "value": "true"},
        {"name": "JHWORKS_LOG_FORMAT", "value": "json"},
        database.environment("JHWORKS_DATABASE_URL"),
        settings.jwt_secret.environment("JHWORKS_JWT_SECRET"),
    ]


def service_manifest(
    settings: ReleaseSettings,
    api_image: str,
    web_image: str,
    revision: str,
) -> dict[str, Any]:
    for image in (api_image, web_image):
        validate_image(image, settings.project_id)
    if not re.fullmatch(re.escape(settings.service) + r"-[a-f0-9]{12}", revision):
        raise ValueError("revision must contain the service name and a 12-character commit SHA")
    return {
        "apiVersion": "serving.knative.dev/v1",
        "kind": "Service",
        "metadata": {
            "name": settings.service,
            "labels": {"cloud.googleapis.com/location": settings.region},
            "annotations": {"run.googleapis.com/maxScale": str(settings.max_instances)},
        },
        "spec": {
            "template": {
                "metadata": {
                    "name": revision,
                    "annotations": {
                        "autoscaling.knative.dev/minScale": "0",
                        "autoscaling.knative.dev/maxScale": str(settings.max_instances),
                        "run.googleapis.com/cpu-throttling": "true",
                        "run.googleapis.com/container-dependencies": '{"web":["api"]}',
                    },
                },
                "spec": {
                    "serviceAccountName": settings.runtime_service_account,
                    "containerConcurrency": settings.concurrency,
                    "timeoutSeconds": 120,
                    "containers": [
                        {
                            "name": "web",
                            "image": web_image,
                            "ports": [{"containerPort": 3000}],
                            "resources": {"limits": {"cpu": "1", "memory": "512Mi"}},
                            "startupProbe": {
                                "tcpSocket": {"port": 3000},
                                "periodSeconds": 5,
                                "failureThreshold": 24,
                            },
                        },
                        {
                            "name": "api",
                            "image": api_image,
                            "env": api_environment(settings),
                            "resources": {"limits": {"cpu": "1", "memory": "512Mi"}},
                            "startupProbe": {
                                "httpGet": {"path": "/api/v1/health/ready", "port": 8000},
                                "timeoutSeconds": 5,
                                "periodSeconds": 5,
                                "failureThreshold": 24,
                            },
                            "livenessProbe": {
                                "httpGet": {"path": "/api/v1/health/live", "port": 8000},
                                "timeoutSeconds": 5,
                                "periodSeconds": 30,
                            },
                        },
                    ],
                },
            },
            # Keep traffic selection explicit; the release runner replaces this with
            # the previous traffic split before creating a candidate revision.
            "traffic": [{"revisionName": revision, "percent": 100}],
        },
    }


def migration_manifest(settings: ReleaseSettings, api_image: str) -> dict[str, Any]:
    validate_image(api_image, settings.project_id)
    return {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Job",
        "metadata": {"name": f"{settings.service}-migrate"},
        "spec": {
            "template": {
                "spec": {
                    "taskCount": 1,
                    "parallelism": 1,
                    "template": {
                        "spec": {
                            "serviceAccountName": settings.migration_service_account,
                            "maxRetries": 0,
                            "timeoutSeconds": "300",
                            "containers": [
                                {
                                    "image": api_image,
                                    "command": ["alembic"],
                                    "args": ["upgrade", "head"],
                                    "env": api_environment(settings, migration=True),
                                    "resources": {"limits": {"cpu": "1", "memory": "512Mi"}},
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
    parser.add_argument("--web-image", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{40}", args.commit):
        parser.error("--commit must be a full commit SHA")
    settings = ReleaseSettings.model_validate_json(args.settings.read_text(encoding="utf-8"))
    revision = f"{settings.service}-{args.commit[:12]}"
    manifests = {
        "service.json": service_manifest(settings, args.api_image, args.web_image, revision),
        "migration.json": migration_manifest(settings, args.api_image),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, manifest in manifests.items():
        (args.output_dir / name).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.ops.demo_maintenance_manifest import MaintenanceSettings, maintenance_manifest

IMAGE = "asia-northeast3-docker.pkg.dev/jhworks-demo/jhworks/api@sha256:" + "a" * 64


def settings_data() -> dict[str, Any]:
    return {
        "project_id": "jhworks-demo",
        "region": "asia-northeast3",
        "job": "jhworks-demo-maintenance",
        "runtime_service_account": "jhworks-runtime@jhworks-demo.iam.gserviceaccount.com",
        "runtime_database": {"name": "runtime-db", "version": "1"},
        "jwt_secret": {"name": "session-secret", "version": "1"},
    }


def test_manifest_is_bounded_private_and_dry_by_default() -> None:
    manifest = maintenance_manifest(MaintenanceSettings.model_validate(settings_data()), IMAGE)
    assert manifest["kind"] == "Job"  # No public Service or IAM bindings are generated.
    spec = manifest["spec"]["template"]["spec"]
    assert spec["taskCount"] == spec["parallelism"] == 1
    task = spec["template"]["spec"]
    assert task["maxRetries"] == 0 and task["timeoutSeconds"] == "120"
    assert task["serviceAccountName"].startswith("jhworks-runtime@")
    container = task["containers"][0]
    assert "--apply" not in container["args"] and container["args"][-1] == "5"
    assert container["resources"]["limits"] == {"cpu": "1", "memory": "512Mi"}
    env = {e["name"]: e for e in container["env"]}
    assert set(
        e["valueFrom"]["secretKeyRef"]["name"] for e in env.values() if "valueFrom" in e
    ) == {"runtime-db", "session-secret"}
    # Resolve fake secret values to validate the actual production app configuration.
    values = {
        e["name"][len("JHWORKS_") :].lower(): e["value"] for e in env.values() if "value" in e
    }
    resolved = Settings(
        _env_file=None,
        **values,
        database_url="postgresql+psycopg://synthetic@localhost/db",
        jwt_secret="x" * 32,
    )
    assert resolved.public_demo_enabled and not resolved.ai_enabled and resolved.cookie_secure
    assert (
        "--apply"
        in maintenance_manifest(
            MaintenanceSettings.model_validate(settings_data()), IMAGE, apply=True
        )["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["args"]
    )


@pytest.mark.parametrize(
    "image",
    [
        IMAGE.replace("@sha256:" + "a" * 64, ":latest"),
        IMAGE.replace("jhworks-demo/", "other-project/"),
        IMAGE.replace("asia-northeast3-", "us-central1-"),
    ],
)
def test_foreign_or_mutable_image_rejected(image: str) -> None:
    with pytest.raises(ValueError):
        maintenance_manifest(MaintenanceSettings.model_validate(settings_data()), image)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("runtime_service_account", "owner@other-project.iam.gserviceaccount.com"),
        ("runtime_database", {"name": "runtime-db", "version": "latest"}),
        ("jwt_secret", {"name": "runtime-db", "version": "1"}),
        ("job", "jhworks-staging-migrate"),
        ("max_retries", 10),
    ],
)
def test_configuration_rejects_unsafe_overrides(key: str, value: Any) -> None:
    data = settings_data()
    data[key] = value
    with pytest.raises(ValidationError):
        MaintenanceSettings.model_validate(data)

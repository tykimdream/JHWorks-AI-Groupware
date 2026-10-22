import copy
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ops.demo_isolation import IsolatedDemoSettings, isolated_demo_manifests
from tests.test_cloud_run_release import API_IMAGE, COMMIT, WEB_IMAGE

ROOT = Path(__file__).resolve().parents[3]


def isolated_settings() -> dict[str, Any]:
    data = json.loads((ROOT / "deploy/cloud-run/isolated-demo.example.json").read_text())
    project = "jhworks-demo"
    data["project_id"] = project
    for key in ("runtime_service_account", "migration_service_account"):
        data[key] = data[key].replace("replace-project", project)
    return dict(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runtime_service_account", "jhworks-runtime@jhworks-demo.iam.gserviceaccount.com"),
        ("migration_service_account", "jhworks-migrate@jhworks-demo.iam.gserviceaccount.com"),
        ("runtime_database", {"name": "jhworks-runtime-database", "version": "1"}),
        ("migration_database", {"name": "jhworks-migration-database", "version": "1"}),
        ("jwt_secret", {"name": "jhworks-session-secret", "version": "1"}),
        ("jwt_secret", {"name": "jhworks-demo-runtime-database", "version": "1"}),
    ],
)
def test_isolated_release_refuses_shared_identity_or_secret(field: str, value: Any) -> None:
    data = isolated_settings()
    data[field] = value
    with pytest.raises(ValueError):
        IsolatedDemoSettings.model_validate(data)


def test_runtime_and_migration_receive_only_their_dedicated_database() -> None:
    config = IsolatedDemoSettings.model_validate(isolated_settings())
    before = copy.deepcopy(config.model_dump())
    manifests = isolated_demo_manifests(config, API_IMAGE, WEB_IMAGE, COMMIT)
    service = manifests["service.json"]
    assert service["metadata"]["annotations"]["run.googleapis.com/invoker-iam-disabled"] == "false"
    service_spec = service["spec"]["template"]["spec"]
    migration = manifests["migration.json"]["spec"]["template"]["spec"]["template"]["spec"]
    maintenance = manifests["maintenance-dry-run.json"]["spec"]["template"]["spec"]
    maintenance = maintenance["template"]["spec"]
    assert service_spec["serviceAccountName"] == maintenance["serviceAccountName"]
    assert migration["serviceAccountName"] != service_spec["serviceAccountName"]
    for spec, container, expected in [
        (service_spec, 1, "jhworks-demo-runtime-database"),
        (maintenance, 0, "jhworks-demo-runtime-database"),
        (migration, 0, "jhworks-demo-migration-database"),
    ]:
        refs = {
            row["valueFrom"]["secretKeyRef"]["name"]
            for row in spec["containers"][container]["env"]
            if "valueFrom" in row
        }
        assert refs == {expected, "jhworks-demo-session-secret"}
    assert "--apply" not in maintenance["containers"][0]["args"]
    assert config.model_dump() == before
    assert "allUsers" not in json.dumps(manifests)


@pytest.mark.parametrize(
    ("field", "value"),
    [("service", "jhworks-staging"), ("max_instances", 2), ("concurrency", 8)],
)
def test_isolated_plan_keeps_existing_demo_resource_guards(field: str, value: Any) -> None:
    data = isolated_settings()
    data[field] = value
    with pytest.raises(ValueError):
        isolated_demo_manifests(
            IsolatedDemoSettings.model_validate(data), API_IMAGE, WEB_IMAGE, COMMIT
        )


def test_sessions_signed_by_separate_deployments_are_not_interchangeable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings
    from app.core.security import create_session_token

    settings = get_settings()
    monkeypatch.setattr(settings, "jwt_secret", "synthetic-private-key-for-isolation-test")
    private = create_session_token("emp_sales_001")
    monkeypatch.setattr(settings, "jwt_secret", "synthetic-public-key-for-isolation-test")
    client.cookies.set(settings.session_cookie_name, private)
    assert client.get("/api/v1/employees/me").status_code == 401
    public = create_session_token("emp_sales_001")
    client.cookies.set(settings.session_cookie_name, public)
    assert client.get("/api/v1/employees/me").status_code == 200
    monkeypatch.setattr(settings, "jwt_secret", "synthetic-private-key-for-isolation-test")
    assert client.get("/api/v1/employees/me").status_code == 401

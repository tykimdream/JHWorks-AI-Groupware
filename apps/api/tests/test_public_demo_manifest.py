import copy
from typing import Any

import pytest

from app.core.config import Settings
from app.ops.cloud_run import ReleaseSettings, service_manifest
from app.ops.public_demo_manifest import public_demo_service_manifest
from tests.test_cloud_run_release import API_IMAGE, COMMIT, WEB_IMAGE, settings_data


def demo_settings() -> dict[str, Any]:
    return {
        **settings_data(),
        "service": "jhworks-demo",
        "frontend_origin": "https://groupware.pikan.dev",
        "max_instances": 1,
        "concurrency": 4,
    }


def test_demo_uses_separate_service_and_hosting_cookie_without_granting_invocation() -> None:
    config = ReleaseSettings.model_validate(demo_settings())
    manifest = public_demo_service_manifest(config, API_IMAGE, WEB_IMAGE, COMMIT)
    assert manifest["kind"] == "Service" and manifest["metadata"]["name"] == "jhworks-demo"
    assert manifest["metadata"]["annotations"] == {
        "run.googleapis.com/maxScale": "1",
        "run.googleapis.com/invoker-iam-disabled": "false",
    }
    assert "bindings" not in manifest and "allUsers" not in str(manifest)
    spec = manifest["spec"]["template"]["spec"]
    assert spec["timeoutSeconds"] == 55 and spec["containerConcurrency"] == 4
    assert spec["serviceAccountName"] == config.runtime_service_account
    env = {row["name"]: row for row in spec["containers"][1]["env"]}
    assert env["JHWORKS_AI_ENABLED"]["value"] == "false"
    assert env["JHWORKS_PUBLIC_EXPENSE_AI_ENABLED"]["value"] == "false"
    assert env["JHWORKS_PUBLIC_DEMO_ENABLED"]["value"] == "true"
    assert env["JHWORKS_SESSION_COOKIE_NAME"]["value"] == "__session"
    refs = {row["valueFrom"]["secretKeyRef"]["name"] for row in env.values() if "valueFrom" in row}
    assert refs == {config.runtime_database.name, config.jwt_secret.name}
    values = {row["name"][8:].lower(): row["value"] for row in env.values() if "value" in row}
    resolved = Settings(
        _env_file=None,
        **values,
        database_url="postgresql+psycopg://synthetic@localhost/db",
        jwt_secret="x" * 32,
    )
    assert resolved.public_demo_enabled and resolved.cookie_secure and not resolved.ai_enabled
    assert not resolved.public_expense_ai_enabled
    assert (
        resolved.session_cookie_name == "__session"
        and resolved.frontend_origin == config.frontend_origin
    )


def test_private_manifest_contract_is_unchanged() -> None:
    config = ReleaseSettings.model_validate(settings_data())
    before = config.model_dump()
    first = service_manifest(config, API_IMAGE, WEB_IMAGE, "jhworks-staging-" + COMMIT[:12])
    public_demo_service_manifest(
        ReleaseSettings.model_validate(demo_settings()), API_IMAGE, WEB_IMAGE, COMMIT
    )
    second = service_manifest(config, API_IMAGE, WEB_IMAGE, "jhworks-staging-" + COMMIT[:12])
    assert first == second and config.model_dump() == before
    assert "JHWORKS_PUBLIC_DEMO_ENABLED" not in {
        e["name"] for e in first["spec"]["template"]["spec"]["containers"][1]["env"]
    }


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("service", "jhworks-staging"),
        ("frontend_origin", "https://foreign.test"),
        ("frontend_origin", "https://groupware.pikan.dev.evil.test"),
        ("max_instances", 2),
        ("concurrency", 8),
    ],
)
def test_demo_refuses_private_service_or_relaxed_bounds(key: str, value: Any) -> None:
    data = copy.deepcopy(demo_settings())
    data[key] = value
    with pytest.raises(ValueError):
        public_demo_service_manifest(
            ReleaseSettings.model_validate(data), API_IMAGE, WEB_IMAGE, COMMIT
        )


@pytest.mark.parametrize(
    "image",
    [
        API_IMAGE.replace("@sha256:" + "a" * 64, ":latest"),
        API_IMAGE.replace("asia-northeast3", "us-central1"),
        API_IMAGE.replace("jhworks-demo/", "foreign-project/"),
    ],
)
def test_demo_refuses_unreviewed_image_location(image: str) -> None:
    with pytest.raises(ValueError):
        public_demo_service_manifest(
            ReleaseSettings.model_validate(demo_settings()), image, WEB_IMAGE, COMMIT
        )


@pytest.mark.parametrize("commit", ["abc123", "A" * 40, COMMIT + " "])
def test_demo_requires_exact_full_commit(commit: str) -> None:
    with pytest.raises(ValueError, match="full commit"):
        public_demo_service_manifest(
            ReleaseSettings.model_validate(demo_settings()), API_IMAGE, WEB_IMAGE, commit
        )


def test_demo_can_enable_budgeted_expense_ai_with_pinned_secret() -> None:
    from app.core.ai_budget import AIBudgetLimits
    from app.ops.cloud_run import SecretVersion

    budget = AIBudgetLimits(
        day_micro_usd=500000,
        month_micro_usd=2000000,
        day_admissions=10,
        scope_day_admissions=5,
        concurrent_requests=1,
    )
    secret = SecretVersion(name="demo-openai", version="1")
    manifest = public_demo_service_manifest(
        ReleaseSettings.model_validate(demo_settings()),
        API_IMAGE,
        WEB_IMAGE,
        COMMIT,
        expense_ai_secret=secret,
        expense_ai_budget=budget,
    )
    env = {row["name"]: row for row in manifest["spec"]["template"]["spec"]["containers"][1]["env"]}
    assert env["JHWORKS_PUBLIC_EXPENSE_AI_ENABLED"]["value"] == "true"
    assert env["JHWORKS_PUBLIC_LEAVE_AI_ENABLED"]["value"] == "true"
    assert env["JHWORKS_OPENAI_API_KEY"]["valueFrom"]["secretKeyRef"] == {
        "name": "demo-openai",
        "key": "1",
    }
    assert (
        AIBudgetLimits.model_validate_json(env["JHWORKS_PUBLIC_EXPENSE_AI_BUDGET"]["value"])
        == budget
    )
    with pytest.raises(ValueError, match="both"):
        public_demo_service_manifest(
            ReleaseSettings.model_validate(demo_settings()),
            API_IMAGE,
            WEB_IMAGE,
            COMMIT,
            expense_ai_secret=secret,
        )

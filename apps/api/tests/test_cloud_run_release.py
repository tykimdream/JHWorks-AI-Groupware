import json
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

import pytest
from pydantic import ValidationError
from sqlalchemy.pool import NullPool, QueuePool

from app.api import dependencies
from app.core.config import Settings, get_settings
from app.core.database import create_database_engine
from app.ops.cloud_run import ReleaseSettings, migration_manifest, service_manifest
from app.ops.cloud_run_release import ReleaseFailure, release

API_IMAGE = "asia-northeast3-docker.pkg.dev/jhworks-demo/images/api@sha256:" + "a" * 64
WEB_IMAGE = "asia-northeast3-docker.pkg.dev/jhworks-demo/images/web@sha256:" + "b" * 64
COMMIT = "c" * 40


def settings_data() -> dict[str, Any]:
    return {
        "project_id": "jhworks-demo",
        "region": "asia-northeast3",
        "service": "jhworks-staging",
        "frontend_origin": "https://jhworks-staging.example.run.app",
        "runtime_service_account": "jhworks-runtime@jhworks-demo.iam.gserviceaccount.com",
        "migration_service_account": "jhworks-migrate@jhworks-demo.iam.gserviceaccount.com",
        "runtime_database": {"name": "runtime-db", "version": "1"},
        "migration_database": {"name": "migration-db", "version": "2"},
        "jwt_secret": {"name": "session-key", "version": "3"},
    }


def test_service_keeps_api_internal_and_ai_disabled() -> None:
    settings = ReleaseSettings.model_validate(settings_data())
    manifest = service_manifest(settings, API_IMAGE, WEB_IMAGE, f"{settings.service}-{COMMIT[:12]}")
    template = manifest["spec"]["template"]
    assert template["metadata"]["annotations"]["autoscaling.knative.dev/minScale"] == "0"
    assert template["metadata"]["annotations"]["autoscaling.knative.dev/maxScale"] == "2"
    web, api = template["spec"]["containers"]
    assert "ports" in web and "ports" not in api
    assert api["startupProbe"]["httpGet"]["path"].endswith("/ready")
    environment = {item["name"]: item for item in api["env"]}
    assert environment["JHWORKS_AI_ENABLED"]["value"] == "false"
    assert "JHWORKS_OPENAI_API_KEY" not in environment
    assert environment["JHWORKS_COOKIE_SECURE"]["value"] == "true"
    assert environment["JHWORKS_DATABASE_URL"]["valueFrom"]["secretKeyRef"]["name"] == "runtime-db"


def test_migration_is_single_run_with_distinct_credentials_and_no_seed() -> None:
    manifest = migration_manifest(ReleaseSettings.model_validate(settings_data()), API_IMAGE)
    spec = manifest["spec"]["template"]["spec"]
    assert spec["taskCount"] == spec["parallelism"] == 1
    task = spec["template"]["spec"]
    assert task["maxRetries"] == 0
    container = task["containers"][0]
    assert container["command"] + container["args"] == ["alembic", "upgrade", "head"]
    database = next(item for item in container["env"] if item["name"] == "JHWORKS_DATABASE_URL")
    assert database["valueFrom"]["secretKeyRef"]["name"] == "migration-db"
    assert task["serviceAccountName"].startswith("jhworks-migrate@")


@pytest.mark.parametrize(
    "image",
    [
        API_IMAGE.replace("@sha256:" + "a" * 64, ":latest"),
        API_IMAGE.replace("jhworks-demo/", "other-project/"),
        "https://example.test/api@sha256:" + "a" * 64,
    ],
)
def test_rejects_mutable_or_foreign_images(image: str) -> None:
    with pytest.raises(ValueError):
        migration_manifest(ReleaseSettings.model_validate(settings_data()), image)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("frontend_origin", "http://unsafe.test"),
        ("frontend_origin", "https://user:pass@unsafe.test"),
        ("frontend_origin", "https://safe.test/path"),
        ("max_instances", 100),
        ("concurrency", 100),
        ("runtime_service_account", "owner@other-project.iam.gserviceaccount.com"),
        ("runtime_database", {"name": "runtime-db", "version": "latest"}),
        ("migration_database", {"name": "runtime-db", "version": "2"}),
    ],
)
def test_release_configuration_fails_closed(field: str, value: Any) -> None:
    data = settings_data()
    data[field] = value
    with pytest.raises(ValidationError):
        ReleaseSettings.model_validate(data)


class FakeCloud:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.migration_fails = False
        self.public = False
        self.missing = False
        self.service_manifest: dict[str, Any] | None = None

    def run(self, command: list[str]) -> str:
        self.commands.append(command)
        if command[1:4] == ["run", "services", "describe"]:
            if self.missing:
                raise subprocess.CalledProcessError(1, command, stderr="NOT_FOUND")
            return json.dumps(
                {
                    "status": {
                        "url": settings_data()["frontend_origin"],
                        "traffic": [
                            {"revisionName": "previous-a", "percent": 60},
                            {"revisionName": "previous-b", "percent": 40},
                        ],
                    }
                }
            )
        if command[1:4] == ["run", "services", "get-iam-policy"]:
            return json.dumps({"bindings": [{"members": ["allUsers"] if self.public else []}]})
        if command[1:4] == ["run", "services", "replace"]:
            self.service_manifest = json.loads(Path(command[4]).read_text(encoding="utf-8"))
            self.missing = False
        if command[1:4] == ["run", "jobs", "execute"] and self.migration_fails:
            raise subprocess.CalledProcessError(1, command, stderr="migration failed")
        if command[1:3] == ["auth", "print-identity-token"]:
            return "test-token"
        return "{}"


def test_success_runs_migration_before_candidate_and_smoke() -> None:
    cloud = FakeCloud()
    observed: list[tuple[str, str]] = []

    def smoke(url: str, token: str) -> dict[str, Any]:
        observed.append((url, token))
        return {"status": "passed"}

    report = release(
        ReleaseSettings.model_validate(settings_data()),
        API_IMAGE,
        WEB_IMAGE,
        COMMIT,
        "verified-backup-1",
        runner=cloud.run,
        smoke=smoke,
    )
    assert report["status"] == "passed"
    commands = [item[1:4] for item in cloud.commands]
    assert commands.index(["run", "jobs", "execute"]) < commands.index(
        ["run", "services", "replace"]
    )
    assert cloud.service_manifest is not None
    assert cloud.service_manifest["spec"]["traffic"] == report["previousTraffic"]
    assert observed == [(settings_data()["frontend_origin"], "test-token")]
    assert "test-token" not in json.dumps(report)


def test_migration_failure_never_changes_application_traffic() -> None:
    cloud = FakeCloud()
    cloud.migration_fails = True
    with pytest.raises(ReleaseFailure) as failure:
        release(
            ReleaseSettings.model_validate(settings_data()),
            API_IMAGE,
            WEB_IMAGE,
            COMMIT,
            "verified-backup-1",
            runner=cloud.run,
        )
    assert failure.value.record["stage"] == "migration"
    assert not any(
        item[1:4] in (["run", "services", "replace"], ["run", "services", "update-traffic"])
        for item in cloud.commands
    )


def test_smoke_failure_restores_previous_split_without_db_downgrade() -> None:
    cloud = FakeCloud()
    with pytest.raises(ReleaseFailure) as failure:
        release(
            ReleaseSettings.model_validate(settings_data()),
            API_IMAGE,
            WEB_IMAGE,
            COMMIT,
            "verified-backup-1",
            runner=cloud.run,
            smoke=lambda _url, _token: {"status": "failed"},
        )
    traffic_commands = [
        item for item in cloud.commands if item[1:4] == ["run", "services", "update-traffic"]
    ]
    assert traffic_commands[-1][-1] == "previous-a=60,previous-b=40"
    assert failure.value.record["rollbackTraffic"] == "restored"
    assert failure.value.record["rollbackSmoke"]["status"] == "failed"
    assert "downgrade" not in json.dumps(cloud.commands)


def test_public_service_is_not_deployed_by_private_staging_runner() -> None:
    cloud = FakeCloud()
    cloud.public = True
    with pytest.raises(ValueError, match="public IAM"):
        release(
            ReleaseSettings.model_validate(settings_data()),
            API_IMAGE,
            WEB_IMAGE,
            COMMIT,
            "verified-backup-1",
            runner=cloud.run,
        )
    assert not any(item[1:3] == ["run", "jobs"] for item in cloud.commands)


def test_bootstrap_requires_explicit_flag() -> None:
    cloud = FakeCloud()
    cloud.missing = True
    with pytest.raises(subprocess.CalledProcessError):
        release(
            ReleaseSettings.model_validate(settings_data()),
            API_IMAGE,
            WEB_IMAGE,
            COMMIT,
            "fresh-synthetic-db",
            runner=cloud.run,
        )
    report = release(
        ReleaseSettings.model_validate(settings_data()),
        API_IMAGE,
        WEB_IMAGE,
        COMMIT,
        "fresh-synthetic-db",
        runner=cloud.run,
        bootstrap=True,
        smoke=lambda _url, _token: {"status": "passed"},
    )
    assert report["previousTraffic"] == []


def test_postgres_pool_is_bounded_or_delegated_to_supabase_without_connecting() -> None:
    settings = Settings(_env_file=None, database_url="postgresql+psycopg://user:pass@localhost/db")
    queue_engine = create_database_engine(settings)
    assert isinstance(queue_engine.pool, QueuePool)
    assert queue_engine.pool.size() == 2
    settings.database_pool_mode = "null"
    null_engine = create_database_engine(settings)
    assert isinstance(null_engine.pool, NullPool)
    queue_engine.dispose()
    null_engine.dispose()


def test_ai_kill_switch_blocks_all_adapters_even_with_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import SecretStr

    monkeypatch.setattr(get_settings(), "ai_enabled", False)
    monkeypatch.setattr(get_settings(), "openai_api_key", SecretStr("synthetic-never-call"))
    for factory in [
        dependencies.get_approval_review_provider,
        dependencies.get_approval_draft_provider,
        dependencies.get_leave_assistant_provider,
        dependencies.get_work_assistant_provider,
        dependencies.get_policy_embedding_provider,
    ]:
        assert type(factory()).__name__.startswith("Unavailable")


def test_transaction_pooler_disables_psycopg_preparation_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import psycopg

    captured: dict[str, Any] = {}

    def no_network_connect(*args: Any, **kwargs: Any) -> NoReturn:
        captured.update(kwargs)
        raise RuntimeError("synthetic connection blocked")

    monkeypatch.setattr(psycopg, "connect", no_network_connect)
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:synthetic@localhost/db?sslmode=require",
        database_pool_mode="null",
        database_disable_prepared_statements=True,
    )
    engine = create_database_engine(settings)
    with pytest.raises(RuntimeError, match="synthetic connection blocked"):
        engine.connect()
    assert captured["prepare_threshold"] is None
    assert captured["sslmode"] == "require"
    engine.dispose()


def test_alembic_offline_accepts_percent_encoded_password_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JHWORKS_ENVIRONMENT", "test")
    monkeypatch.setenv(
        "JHWORKS_DATABASE_URL",
        "postgresql+psycopg://user:synthetic%40password@localhost/db",
    )
    monkeypatch.setenv("JHWORKS_OPENAI_API_KEY", "")
    monkeypatch.setenv("JHWORKS_AI_ENABLED", "false")
    # The later historical JSON data migration cannot render offline literal SQL.
    # This isolates URL parsing and the initial schema/vector migration contract.
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "alembic", "upgrade", "c7f3a91d42e8", "--sql"],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert "CREATE TABLE approvals" in result.stdout
    assert "c7f3a91d42e8" in result.stdout

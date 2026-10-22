"""Offline demo deployment plan with dedicated identities and secret references."""

import argparse
import json
from pathlib import Path
from typing import Any, Self

from pydantic import model_validator

from app.ops.cloud_run import ReleaseSettings, migration_manifest
from app.ops.demo_maintenance_manifest import MaintenanceSettings, maintenance_manifest
from app.ops.public_demo_manifest import public_demo_service_manifest


class IsolatedDemoSettings(ReleaseSettings):
    @model_validator(mode="after")
    def dedicated_references(self) -> Self:
        accounts = {
            self.runtime_service_account: "jhworks-demo-runtime",
            self.migration_service_account: "jhworks-demo-migrate",
        }
        if any(
            account != f"{name}@{self.project_id}.iam.gserviceaccount.com"
            for account, name in accounts.items()
        ):
            raise ValueError("Use separate demo runtime and migration identities")
        if (
            self.runtime_database.name != "jhworks-demo-runtime-database"
            or self.migration_database.name != "jhworks-demo-migration-database"
            or self.jwt_secret.name != "jhworks-demo-session-secret"
        ):
            raise ValueError("Use the three dedicated demo secrets, not staging references")
        return self


def isolated_demo_manifests(
    settings: IsolatedDemoSettings, api_image: str, web_image: str, commit: str
) -> dict[str, dict[str, Any]]:
    # Service validation also checks the fixed host/service/resource/image bounds.
    service = public_demo_service_manifest(settings, api_image, web_image, commit)
    maintenance = MaintenanceSettings(
        project_id=settings.project_id,
        region=settings.region,
        job="jhworks-demo-maintenance",
        runtime_service_account=settings.runtime_service_account,
        runtime_database=settings.runtime_database,
        jwt_secret=settings.jwt_secret,
    )
    return {
        "service.json": service,
        "migration.json": migration_manifest(settings, api_image),
        "maintenance-dry-run.json": maintenance_manifest(maintenance, api_image),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--api-image", required=True)
    parser.add_argument("--web-image", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    settings = IsolatedDemoSettings.model_validate_json(args.settings.read_text(encoding="utf-8"))
    manifests = isolated_demo_manifests(settings, args.api_image, args.web_image, args.commit)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, manifest in manifests.items():
        (args.output_dir / name).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

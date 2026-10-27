"""Render a separate demo Service for private rehearsal; never changes IAM or DNS."""

import argparse
import json
import re
from pathlib import Path
from typing import Any

from app.core.ai_budget import AIBudgetLimits
from app.core.config import Settings
from app.ops.cloud_run import ReleaseSettings, SecretVersion, service_manifest

DEMO_SERVICE = "jhworks-demo"
DEMO_ORIGIN = "https://groupware.pikan.dev"


def public_demo_service_manifest(
    settings: ReleaseSettings,
    api_image: str,
    web_image: str,
    commit: str,
    *,
    expense_ai_secret: SecretVersion | None = None,
    expense_ai_budget: AIBudgetLimits | None = None,
) -> dict[str, Any]:
    if (
        settings.service != DEMO_SERVICE
        or settings.frontend_origin != DEMO_ORIGIN
        or settings.max_instances != 1
        or settings.concurrency > 4
    ):
        raise ValueError("Demo requires its dedicated service/origin, max=1 and concurrency<=4")
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Demo requires a full commit SHA")
    if any(
        not image.startswith(f"{settings.region}-docker.pkg.dev/")
        for image in (api_image, web_image)
    ):
        raise ValueError("Images must be in the configured region")
    if (expense_ai_secret is None) != (expense_ai_budget is None):
        raise ValueError("Expense AI requires both a secret version and an explicit budget")
    if expense_ai_budget is not None:
        # Reuse the runtime's rollout ceilings before generating a deployable manifest.
        Settings(
            _env_file=None,
            public_demo_enabled=True,
            ai_enabled=False,
            public_expense_ai_enabled=True,
            public_expense_ai_budget=expense_ai_budget,
        )
    manifest = service_manifest(settings, api_image, web_image, f"{DEMO_SERVICE}-{commit[:12]}")
    # Enabling the demo's application mode does not grant Cloud Run invocation.
    # Public IAM and Hosting rewrites require a separate operational approval.
    manifest["metadata"]["annotations"]["run.googleapis.com/invoker-iam-disabled"] = "false"
    spec = manifest["spec"]["template"]["spec"]
    spec["timeoutSeconds"] = 55
    api = next(container for container in spec["containers"] if container["name"] == "api")
    api["env"].extend(
        [
            {"name": "JHWORKS_PUBLIC_DEMO_ENABLED", "value": "true"},
            {
                "name": "JHWORKS_PUBLIC_EXPENSE_AI_ENABLED",
                "value": "true" if expense_ai_secret else "false",
            },
            {
                "name": "JHWORKS_PUBLIC_LEAVE_AI_ENABLED",
                "value": "true" if expense_ai_secret else "false",
            },
            {"name": "JHWORKS_SESSION_COOKIE_NAME", "value": "__session"},
            {"name": "JHWORKS_DEMO_STARTS_PER_DAY", "value": "20"},
            {"name": "JHWORKS_DEMO_RETAINED_WORKSPACES", "value": "30"},
            {"name": "JHWORKS_DEMO_TTL_MINUTES", "value": "15"},
        ]
    )
    if expense_ai_secret is not None and expense_ai_budget is not None:
        api["env"].extend(
            [
                expense_ai_secret.environment("JHWORKS_OPENAI_API_KEY"),
                {
                    "name": "JHWORKS_PUBLIC_EXPENSE_AI_BUDGET",
                    "value": expense_ai_budget.model_dump_json(),
                },
            ]
        )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--api-image", required=True)
    parser.add_argument("--web-image", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--expense-ai-secret", type=Path, help="JSON secret name and pinned version"
    )
    parser.add_argument("--expense-ai-budget", type=Path, help="JSON explicit rollout budget")
    args = parser.parse_args()
    settings = ReleaseSettings.model_validate_json(args.settings.read_text(encoding="utf-8"))
    secret = (
        SecretVersion.model_validate_json(args.expense_ai_secret.read_text())
        if args.expense_ai_secret
        else None
    )
    budget = (
        AIBudgetLimits.model_validate_json(args.expense_ai_budget.read_text())
        if args.expense_ai_budget
        else None
    )
    manifest = public_demo_service_manifest(
        settings,
        args.api_image,
        args.web_image,
        args.commit,
        expense_ai_secret=secret,
        expense_ai_budget=budget,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

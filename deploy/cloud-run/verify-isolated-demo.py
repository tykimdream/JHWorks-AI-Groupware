"""Operator smoke test: creates two synthetic visits, one approval and one feedback.

Run only after the approved private isolated rollout. No infrastructure/DB admin
commands, private fixture passwords, LLM calls, cleanup or automatic HTTP retry.
"""

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import httpx

PROJECT = "jhworks-staging-tykimdream"
REVISION = "jhworks-demo-75d5e8a98fb2-3c51785fafdb"
BASE = "https://jhworks-demo-968398406137.asia-northeast3.run.app"
ORIGIN = "https://groupware.pikan.dev"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Inspect existing output and writes before any repeat")
    checks: list[dict[str, str | int]] = []
    stage = "private_service_guard"
    created = {"visits": 0, "approvals": 0, "feedback": 0}
    try:

        def command(arguments: list[str]) -> str:
            return subprocess.run(arguments, capture_output=True, text=True, check=True).stdout

        state = json.loads(
            command(
                [
                    "gcloud",
                    "run",
                    "services",
                    "describe",
                    "jhworks-demo",
                    "--project=" + PROJECT,
                    "--region=asia-northeast3",
                    "--format=json",
                ]
            )
        )
        spec = state["spec"]["template"]["spec"]
        assert state["spec"]["template"]["metadata"]["name"] == REVISION
        assert [
            (r["revisionName"], r.get("percent", 0))
            for r in state["status"]["traffic"]
            if r.get("percent", 0)
        ] == [(REVISION, 100)]
        assert (
            spec["serviceAccountName"] == f"jhworks-demo-runtime@{PROJECT}.iam.gserviceaccount.com"
        )
        assert (
            state["metadata"]["annotations"].get("run.googleapis.com/invoker-iam-disabled")
            != "true"
        )
        assert state["metadata"]["annotations"]["run.googleapis.com/maxScale"] == "1"
        env = next(c for c in spec["containers"] if c["name"] == "api")["env"]
        assert next(v for v in env if v["name"] == "JHWORKS_AI_ENABLED")["value"] == "false"
        refs = {
            v["valueFrom"]["secretKeyRef"]["name"]: v["valueFrom"]["secretKeyRef"]["key"]
            for v in env
            if "valueFrom" in v
        }
        assert refs == {"jhworks-demo-runtime-database": "1", "jhworks-demo-session-secret": "1"}
        policy = json.loads(
            command(
                [
                    "gcloud",
                    "run",
                    "services",
                    "get-iam-policy",
                    "jhworks-demo",
                    "--project=" + PROJECT,
                    "--region=asia-northeast3",
                    "--format=json",
                ]
            )
        )
        assert not any(
            m in {"allUsers", "allAuthenticatedUsers"}
            for b in policy.get("bindings", [])
            for m in b.get("members", [])
        )
        token = command(["gcloud", "auth", "print-identity-token"]).strip()
        assert token
        headers = {"Origin": ORIGIN, "X-Serverless-Authorization": "Bearer " + token}
        with (
            httpx.Client(base_url=BASE, headers=headers, timeout=60, trust_env=False) as first,
            httpx.Client(base_url=BASE, headers=headers, timeout=60, trust_env=False) as second,
        ):

            def request(
                name: str,
                client: httpx.Client,
                method: str,
                path: str,
                status: int = 200,
                **kwargs: Any,
            ) -> httpx.Response:
                nonlocal stage
                stage = name
                response = client.request(method, "/api/v1" + path, **kwargs)
                assert response.status_code == status
                checks.append({"name": name, "status": response.status_code})
                return response

            ready = request("ready", first, "GET", "/health/ready").json()
            assert ready["status"] == "ready" and ready["checks"]["database"] == "ok"
            assert request("configuration", first, "GET", "/demo/configuration").json()["enabled"]
            response = request("first_visit", first, "POST", "/demo/start")
            created["visits"] += 1
            cookie = response.headers["set-cookie"].lower()
            assert cookie.startswith("__session=") and all(
                v in cookie for v in ("secure", "httponly", "samesite=lax")
            )
            author = response.json()["employee"]
            assert request("me", first, "GET", "/employees/me").json()["id"] == author["id"]
            request(
                "csrf",
                first,
                "POST",
                "/demo/role",
                403,
                headers={"Origin": "https://untrusted.invalid"},
                json={"role": "manager"},
            )
            draft = request(
                "draft",
                first,
                "POST",
                "/approvals",
                201,
                json={
                    "type": "GENERAL",
                    "title": "Synthetic isolated rollout validation",
                    "content": "Synthetic demo workflow only.",
                    "details": {"kind": "GENERAL"},
                },
            ).json()
            created["approvals"] += 1
            path = "/approvals/" + draft["id"]
            pending = request(
                "submit", first, "POST", path + "/submit", json={"version": draft["version"]}
            ).json()
            assert pending["status"] == "PENDING"
            request("manager", first, "POST", "/demo/role", json={"role": "manager"})
            assigned = request("assigned", first, "GET", "/approvals", params={"scope": "assigned"})
            assert any(row["id"] == draft["id"] for row in assigned.json()["items"])
            approved = request(
                "approve", first, "POST", path + "/approve", json={"version": pending["version"]}
            ).json()
            assert approved["status"] == "APPROVED"
            request("author", first, "POST", "/demo/role", json={"role": "author"})
            payload = {
                "category": "usability",
                "screen": "approvals",
                "consent": True,
                "message": "Synthetic isolated rehearsal feedback: approval action was clear.",
            }
            receipt = request("feedback", first, "POST", "/demo/feedback", json=payload).json()
            created["feedback"] += 1
            assert (
                request("feedback_dedupe", first, "POST", "/demo/feedback", json=payload).json()
                == receipt
            )
            request("feedback_list_denied", first, "GET", "/demo/feedback", 405)
            other = request("second_visit", second, "POST", "/demo/start").json()["employee"]
            created["visits"] += 1
            assert other["departmentId"] != author["departmentId"]
            request("cross_workspace_denied", second, "GET", path, 403)
            for index, client in enumerate((first, second)):
                request("logout_" + str(index), client, "POST", "/auth/logout")
                request("logged_out_" + str(index), client, "GET", "/employees/me", 401)
        result = {"status": "passed", "checks": checks, "syntheticCreated": created}
    except Exception as exc:
        # HTTP/subprocess exceptions can retain tokens and response content.
        result = {
            "status": "failed",
            "stage": stage,
            "errorType": type(exc).__name__,
            "checks": checks,
            "syntheticCreated": created,
            "retry": "inspect_partial_writes_first",
        }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

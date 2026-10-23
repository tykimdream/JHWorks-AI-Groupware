"""Bounded private/demo HTTP session probe. Metadata-only unless --execute.

Execution reads one fixed private signing Secret and creates one synthetic demo
workspace. No passwords, demo signing keys, arbitrary URLs or automatic retries.
"""

import argparse
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import jwt

from app.ops.session_key_boundary import PROJECT, command, inspect_references

PRIVATE_ACTOR = "stg_author_001"


@dataclass(frozen=True)
class Target:
    service: str
    base: str
    origin: str
    cookie: str
    public_demo: bool
    database_secret: str


PRIVATE_BASE = "https://jhworks-staging-968398406137.asia-northeast3.run.app"
DEMO_BASE = "https://jhworks-demo-968398406137.asia-northeast3.run.app"
PRIVATE = Target("jhworks-staging", PRIVATE_BASE, PRIVATE_BASE, "jhworks_session", False,
                 "jhworks-runtime-database")
DEMO = Target("jhworks-demo", DEMO_BASE, "https://groupware.pikan.dev", "__session", True,
              "jhworks-demo-runtime-database")


class BoundaryCheckError(Exception):
    pass


def require(condition: bool) -> None:
    if not condition:
        raise BoundaryCheckError()


def inspect_targets(run: Callable[[list[str]], str]) -> None:
    states: dict[str, Any] = {}

    def capture(arguments: list[str]) -> str:
        result = run(arguments)
        if arguments[:3] == ["run", "services", "describe"]:
            states[arguments[3]] = json.loads(result)
        return result

    inspect_references(capture)
    policy = json.loads(run(["projects", "get-iam-policy", PROJECT, "--format=json"]))
    require(not any(member in {"allUsers", "allAuthenticatedUsers"}
                    for binding in policy.get("bindings", [])
                    for member in binding.get("members", [])))
    for target in (PRIVATE, DEMO):
        api = next(c for c in states[target.service]["spec"]["template"]["spec"]["containers"]
                   if c["name"] == "api")
        env = {e["name"]: e for e in api["env"]}
        require(env["JHWORKS_FRONTEND_ORIGIN"].get("value") == target.origin)
        require(env.get("JHWORKS_SESSION_COOKIE_NAME", {}).get("value", "jhworks_session")
                == target.cookie)
        require(env.get("JHWORKS_PUBLIC_DEMO_ENABLED", {}).get("value", "false")
                == str(target.public_demo).lower())
        require(env["JHWORKS_COOKIE_SECURE"].get("value") == "true")
        require(env["JHWORKS_DATABASE_URL"]["valueFrom"]["secretKeyRef"]
                == {"name": target.database_secret, "key": "1"})


def create_client() -> httpx.Client:
    return httpx.Client(timeout=60, trust_env=False, follow_redirects=False)


def exercise(
    client: httpx.Client, report: dict[str, Any], identity_token: str,
    load_private_key: Callable[[], str],
) -> None:
    sessions: dict[str, str] = {}
    logout_attempted: set[str] = set()

    def request(
        name: str, target: Target, method: str, path: str, expected: int,
        token: str | None = None,
    ) -> httpx.Response:
        report["stage"] = name
        # Never let a response CookieJar supply an unnoticed same-service token
        # alongside the foreign token under test.
        client.cookies.clear()
        headers = {"Origin": target.origin,
                   "X-Serverless-Authorization": "Bearer " + identity_token}
        if token is not None:
            headers["Cookie"] = target.cookie + "=" + token
        report["httpRequests"] += 1
        response = client.request(method, target.base + "/api/v1" + path, headers=headers)
        report["checks"].append({"name": name, "status": response.status_code})
        require(response.status_code == expected)
        cache = response.headers.get("cache-control", "").lower()
        require("private" in cache and "no-store" in cache)
        return response

    def me(name: str, target: Target, token: str, actor: str) -> None:
        require(request(name, target, "GET", "/employees/me", 200, token).json()["id"] == actor)

    def denied(name: str, target: Target, token: str | None, *, cross: bool = False) -> None:
        error = request(name, target, "GET", "/employees/me", 401, token).json()["error"]
        require(error["code"] == "AUTHENTICATION_REQUIRED")
        if cross:
            require(error["message"] == "The session is invalid or expired")

    def logout(name: str, target: Target) -> None:
        logout_attempted.add(target.service)
        response = request(name, target, "POST", "/auth/logout", 200, sessions[target.service])
        require(response.json().get("success") is True)

    try:
        for target in (PRIVATE, DEMO):
            config = request(target.service + "_configuration", target, "GET",
                             "/demo/configuration", 200).json()
            require(config["enabled"] is target.public_demo)
        report["stage"] = "private_session_key"
        key = load_private_key()
        require(len(key) >= 32)
        now = int(datetime.now(UTC).timestamp())
        private_token = jwt.encode({"sub": PRIVATE_ACTOR, "type": "session", "iat": now,
                                    "exp": now + 60}, key, algorithm="HS256")
        sessions[PRIVATE.service] = private_token
        me("private_own_before", PRIVATE, private_token, PRIVATE_ACTOR)

        report["demoStartAttempted"] = True
        report["demoStartOutcomeUnknown"] = True
        response = request("demo_start", DEMO, "POST", "/demo/start", 200)
        cookies = [c for c in response.cookies.jar if c.name == DEMO.cookie]
        require(len(cookies) == 1 and cookies[0].value is not None)
        demo_token = str(cookies[0].value)
        sessions[DEMO.service] = demo_token
        require(cookies[0].secure and cookies[0].has_nonstandard_attr("HttpOnly")
                and cookies[0].get_nonstandard_attr("SameSite") == "lax")
        data = response.json()
        actor = data["employee"]["id"]
        require(isinstance(actor, str) and re.fullmatch(r"demo_author_[0-9a-f]{32}", actor)
                is not None)
        require(type(data["expiresAtEpoch"]) is int
                and data["expiresAtEpoch"] > int(datetime.now(UTC).timestamp()))
        report["syntheticCreated"]["visits"] = 1
        report["workspaceId"] = "demo_" + actor.removeprefix("demo_author_")
        report["expiresAtEpoch"] = data["expiresAtEpoch"]
        report["demoStartOutcomeUnknown"] = False
        me("demo_own_before", DEMO, demo_token, actor)

        denied("demo_session_on_private", PRIVATE, demo_token, cross=True)
        denied("private_session_on_demo", DEMO, private_token, cross=True)
        me("private_own_after", PRIVATE, private_token, PRIVATE_ACTOR)
        me("demo_own_after", DEMO, demo_token, actor)
        report["crossSessionsRejected"] = 2
        report["ownSessionChecksPassed"] = 4

        for target in (PRIVATE, DEMO):
            logout(target.service + "_logout", target)
            denied(target.service + "_without_cookie", target, None)
    finally:
        failure_stage = report["stage"]
        for target in (PRIVATE, DEMO):
            if target.service in sessions and target.service not in logout_attempted:
                try:
                    logout(target.service + "_cleanup_logout", target)
                except Exception as exc:
                    report.setdefault("cleanupErrors", []).append({
                        "service": target.service, "errorType": type(exc).__name__,
                    })
        client.cookies.clear()
        report["stage"] = failure_stage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report: dict[str, Any] = {
        "status": "running", "stage": "service_guards", "executed": args.execute,
        "secretPayloadsRead": 0, "identityTokensRead": 0, "httpRequests": 0,
        "demoStartAttempted": False, "demoStartOutcomeUnknown": False,
        "syntheticCreated": {"visits": 0, "approvals": 0, "feedback": 0},
        "checks": [],
    }
    args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        parser.error("Inspect the existing attempt/result before any repeat")
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(json.dumps(report) + "\n")
        output.flush()
        try:
            inspect_targets(command)
            report["serviceTargetsVerified"] = 2
            if args.execute:
                report["stage"] = "cloud_identity"
                identity = command(["auth", "print-identity-token"]).strip()
                report["identityTokensRead"] = 1
                require(bool(identity))

                def load_key() -> str:
                    key = command(["secrets", "versions", "access", "1",
                                   "--secret=jhworks-session-secret", "--project=" + PROJECT])
                    report["secretPayloadsRead"] += 1
                    return key

                with create_client() as client:
                    exercise(client, report, identity, load_key)
            report.update(status="passed", stage="complete")
        except Exception as exc:
            report.update(status="failed", errorType=type(exc).__name__)
        report["observedAt"] = datetime.now(UTC).isoformat()
        output.seek(0)
        output.truncate()
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

import json
import stat
import sys
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.security import create_session_token
from app.models.demo_workspace import DemoWorkspace
from app.ops import session_http_boundary as probe
from app.ops.session_key_boundary import PROJECT
from tests.test_session_key_boundary import run_fixture

PRIVATE_KEY = "synthetic-private-" + "a" * 32
DEMO_KEY = "synthetic-demo-" + "b" * 32
DEMO_ACTOR = "demo_author_" + "f" * 32


def metadata(arguments: list[str]) -> str:
    if arguments[:2] == ["projects", "get-iam-policy"]:
        return json.dumps({"bindings": []})
    state = json.loads(run_fixture(arguments))
    if arguments[2] == "describe":
        target = probe.PRIVATE if arguments[3] == probe.PRIVATE.service else probe.DEMO
        state["spec"]["template"]["spec"]["containers"][0]["env"].extend([
            {"name": "JHWORKS_FRONTEND_ORIGIN", "value": target.origin},
            {"name": "JHWORKS_SESSION_COOKIE_NAME", "value": target.cookie},
            {"name": "JHWORKS_PUBLIC_DEMO_ENABLED", "value": str(target.public_demo).lower()},
            {"name": "JHWORKS_COOKIE_SECURE", "value": "true"},
            {"name": "JHWORKS_DATABASE_URL", "valueFrom": {
                "secretKeyRef": {"name": target.database_secret, "key": "1"}}},
        ])
    return json.dumps(state)


class SyntheticServices:
    def __init__(self, failure: str | None = None) -> None:
        self.failure = failure
        self.requests: list[httpx.Request] = []
        self.starts = 0
        self.demo_own_reads = 0
        self.demo_key = PRIVATE_KEY if failure == "shared_key" else DEMO_KEY
        self.tokens: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        is_private = request.url.host == httpx.URL(probe.PRIVATE_BASE).host
        target = probe.PRIVATE if is_private else probe.DEMO
        assert str(request.url).startswith(target.base + "/api/v1/")
        assert request.headers["Origin"] == target.origin
        assert request.headers["X-Serverless-Authorization"] == "Bearer synthetic-cloud-identity"
        headers = {"cache-control": "private, no-store"}

        def response(status: int, data: dict[str, Any]) -> httpx.Response:
            return httpx.Response(status, json=data, headers=headers)

        def denied(message: str) -> httpx.Response:
            return response(401, {"error": {"code": "AUTHENTICATION_REQUIRED", "message": message}})

        if request.url.path.endswith("/demo/configuration"):
            assert "cookie" not in request.headers
            enabled = target.public_demo
            if self.failure == "mode":
                enabled = not enabled
            return response(200, {"enabled": enabled})
        if request.url.path.endswith("/demo/start"):
            self.starts += 1
            assert target == probe.DEMO and self.starts == 1
            assert "cookie" not in request.headers
            if self.failure == "lost_start_response":
                raise httpx.ReadTimeout("synthetic token must not enter output", request=request)
            now = int(datetime.now(UTC).timestamp())
            token = jwt.encode({"sub": DEMO_ACTOR, "iat": now, "exp": now + 900,
                                "type": "session"}, self.demo_key, algorithm="HS256")
            self.tokens.append(token)
            secure = "" if self.failure == "insecure_cookie" else "; Secure"
            headers["set-cookie"] = f"__session={token}; Path=/; HttpOnly; SameSite=lax{secure}"
            return response(200, {"employee": {"id": DEMO_ACTOR}, "expiresAtEpoch": now + 900})
        if request.url.path.endswith("/auth/logout"):
            assert request.method == "POST"
            return response(200, {"success": True})
        assert request.url.path.endswith("/employees/me") and request.method == "GET"
        cookie = SimpleCookie()
        cookie.load(request.headers.get("cookie", ""))
        if target.cookie not in cookie:
            return denied("Authentication is required")
        # No own-session CookieJar can mask a foreign cookie.
        assert list(cookie) == [target.cookie]
        token = cookie[target.cookie].value
        self.tokens.append(token)
        key = PRIVATE_KEY if target == probe.PRIVATE else self.demo_key
        try:
            payload = jwt.decode(token, key, algorithms=["HS256"])
        except jwt.InvalidSignatureError:
            message = "The session is invalid or expired"
            if self.failure == "wrong_cross_error":
                message = "The employee account is unavailable"
            return denied(message)
        expected_actor = probe.PRIVATE_ACTOR if target == probe.PRIVATE else DEMO_ACTOR
        if payload["sub"] != expected_actor:
            return denied("The employee account is unavailable")
        if target == probe.DEMO:
            self.demo_own_reads += 1
            if self.failure == "expired_after_cross" and self.demo_own_reads == 2:
                return denied("The session is invalid or expired")
        return response(200, {"id": expected_actor})


def invoke(
    monkeypatch: pytest.MonkeyPatch, output: Path, *, execute: bool = True,
    failure: str | None = None,
) -> tuple[int, dict[str, Any], SyntheticServices, list[list[str]]]:
    calls: list[list[str]] = []
    services = SyntheticServices(failure)

    def command(arguments: list[str]) -> str:
        calls.append(arguments)
        if arguments[:2] == ["auth", "print-identity-token"]:
            return "synthetic-cloud-identity\n"
        if arguments[0] == "secrets":
            assert arguments == ["secrets", "versions", "access", "1",
                                 "--secret=jhworks-session-secret", "--project=" + PROJECT]
            return PRIVATE_KEY
        return metadata(arguments)

    def client() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(services.handle), follow_redirects=False)

    monkeypatch.setattr(probe, "command", command)
    monkeypatch.setattr(probe, "create_client", client)
    monkeypatch.setattr(sys, "argv", ["probe", "--output", str(output)]
                        + (["--execute"] if execute else []))
    code = probe.main()
    return code, json.loads(output.read_text()), services, calls


def test_metadata_only_does_not_read_credentials_or_start_http(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    code, report, services, calls = invoke(monkeypatch, tmp_path / "report.json", execute=False)
    assert code == 0 and report["executed"] is False
    assert report["httpRequests"] == 0 and report["secretPayloadsRead"] == 0
    assert not services.requests and all(c[0] not in {"secrets", "auth"} for c in calls)


@pytest.mark.parametrize("change", ["origin", "cookie", "database", "mode", "public_project"])
def test_target_drift_stops_before_secret_identity_or_http(
    change: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    def command(arguments: list[str]) -> str:
        assert arguments[0] not in {"secrets", "auth"}
        state = json.loads(metadata(arguments))
        if change == "public_project" and arguments[0] == "projects":
            state["bindings"] = [{"members": ["allAuthenticatedUsers"]}]
        elif arguments[:3] == ["run", "services", "describe"]:
            env = {e["name"]: e for e in state["spec"]["template"]["spec"]["containers"][0]["env"]}
            if change == "origin":
                env["JHWORKS_FRONTEND_ORIGIN"]["value"] = "https://untrusted.invalid"
            elif change == "cookie":
                env["JHWORKS_SESSION_COOKIE_NAME"]["value"] = "unexpected"
            elif change == "database":
                env["JHWORKS_DATABASE_URL"]["valueFrom"]["secretKeyRef"]["key"] = "latest"
            elif change == "mode":
                env["JHWORKS_PUBLIC_DEMO_ENABLED"]["value"] = "true"
        return json.dumps(state)

    monkeypatch.setattr(probe, "command", command)
    monkeypatch.setattr(probe, "create_client", lambda: pytest.fail("No HTTP before guards pass"))
    path = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["probe", "--execute", "--output", str(path)])
    assert probe.main() == 1
    report = json.loads(path.read_text())
    assert report["stage"] == "service_guards"
    for field in ("secretPayloadsRead", "identityTokensRead", "httpRequests"):
        assert report[field] == 0


def test_four_positive_controls_cross_rejection_and_no_secret_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "report.json"
    code, report, services, calls = invoke(monkeypatch, path)
    assert code == 0 and report["status"] == "passed"
    assert report["ownSessionChecksPassed"] == 4 and report["crossSessionsRejected"] == 2
    assert report["httpRequests"] == len(services.requests) == 13
    assert services.starts == 1 and services.demo_own_reads == 2
    assert report["syntheticCreated"] == {"visits": 1, "approvals": 0, "feedback": 0}
    assert not report["demoStartOutcomeUnknown"]
    assert report["secretPayloadsRead"] == sum(c[0] == "secrets" for c in calls) == 1
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    output = path.read_text() + capsys.readouterr().out
    assert PRIVATE_KEY not in output and "synthetic-cloud-identity" not in output
    assert all(token not in output for token in services.tokens)


@pytest.mark.parametrize("failure", ["shared_key", "wrong_cross_error", "expired_after_cross",
                                     "insecure_cookie", "lost_start_response"])
def test_failures_cannot_be_reported_as_boundary_success_and_never_retry_start(
    failure: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    code, report, services, calls = invoke(monkeypatch, tmp_path / "report.json", failure=failure)
    assert code == 1 and report["status"] == "failed"
    assert services.starts == 1 and sum(c[0] == "secrets" for c in calls) == 1
    logout_hosts = [r.url.host for r in services.requests if r.url.path.endswith("/auth/logout")]
    assert len(logout_hosts) == len(set(logout_hosts))  # No logout retry, even during cleanup.
    if failure == "lost_start_response":
        assert report["stage"] == "demo_start" and report["demoStartOutcomeUnknown"] is True
        assert report["syntheticCreated"]["visits"] == 0
    if failure == "expired_after_cross":
        assert "crossSessionsRejected" not in report


def test_live_mode_mismatch_stops_before_secret_read_or_demo_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    code, report, services, calls = invoke(monkeypatch, tmp_path / "report.json", failure="mode")
    assert code == 1 and services.starts == 0
    assert report["secretPayloadsRead"] == 0 and all(c[0] != "secrets" for c in calls)


def test_existing_attempt_blocks_all_external_actions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    path = tmp_path / "report.json"
    path.write_text('{"status":"running"}')
    monkeypatch.setattr(probe, "command", lambda _: pytest.fail("No external call on repeat"))
    monkeypatch.setattr(sys, "argv", ["probe", "--execute", "--output", str(path)])
    with pytest.raises(SystemExit) as error:
        probe.main()
    assert error.value.code == 2 and json.loads(path.read_text())["status"] == "running"


def test_real_api_rejects_cross_signatures_even_when_both_actors_exist(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session],
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_enabled", False)
    monkeypatch.setattr(settings, "public_demo_enabled", False)
    monkeypatch.setattr(settings, "jwt_secret", PRIVATE_KEY)
    private = create_session_token("emp_sales_001")

    def me(token: str, expected: int) -> dict[str, Any]:
        client.cookies.clear()
        client.cookies.set(settings.session_cookie_name, token)
        response = client.get("/api/v1/employees/me")
        assert response.status_code == expected
        return dict(response.json())

    assert me(private, 200)["id"] == "emp_sales_001"
    monkeypatch.setattr(settings, "public_demo_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", DEMO_KEY)
    client.cookies.clear()
    start = client.post("/api/v1/demo/start")
    assert start.status_code == 200
    demo = start.cookies[settings.session_cookie_name]
    actor = start.json()["employee"]["id"]
    assert me(demo, 200)["id"] == actor
    assert me(private, 401)["error"]["message"] == "The session is invalid or expired"
    monkeypatch.setattr(settings, "public_demo_enabled", False)
    monkeypatch.setattr(settings, "jwt_secret", PRIVATE_KEY)
    assert me(demo, 401)["error"]["message"] == "The session is invalid or expired"
    assert me(private, 200)["id"] == "emp_sales_001"
    monkeypatch.setattr(settings, "public_demo_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", DEMO_KEY)
    assert me(demo, 200)["id"] == actor
    with session_factory() as db:
        assert db.scalar(select(DemoWorkspace.requests_used)) == 2

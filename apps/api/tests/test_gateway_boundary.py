from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from app.main import app


@pytest.mark.parametrize(
    ("method", "path", "body", "origin", "status"),
    [
        ("GET", "/api/v1/employees/me", None, None, 401),
        ("POST", "/api/v1/auth/login", {}, None, 422),
        ("POST", "/api/v1/auth/login",
         {"email": "seojin.yoon@jhworks.test", "password": "incorrect"}, None, 401),
        ("POST", "/api/v1/auth/logout", None, "https://untrusted.invalid", 403),
    ],
)
def test_gateway_does_not_store_denied_or_invalid_responses(
    client: TestClient, method: str, path: str, body: dict[str, str] | None,
    origin: str | None, status: int,
) -> None:
    response = client.request(method, path, json=body, headers={"Origin": origin} if origin else {})
    assert response.status_code == status
    assert "no-store" in response.headers.get("Cache-Control", "")


def test_private_identity_responses_remain_uncacheable_for_different_users(
    client: TestClient, login: Callable[[TestClient, str], None],
) -> None:
    identities = []
    for email in ("seojin.yoon@jhworks.test", "doyun.choi@jhworks.test"):
        client.cookies.clear()
        login(client, email)
        response = client.get("/api/v1/employees/me")
        assert response.status_code == 200
        assert "no-store" in response.headers.get("Cache-Control", "")
        identities.append(response.json()["id"])
    assert identities[0] != identities[1]


def test_firebase_cookie_uses_startup_configuration() -> None:
    import os
    import subprocess
    import sys
    from pathlib import Path

    environment = {
        **os.environ,
        "JHWORKS_ENVIRONMENT": "test",
        "JHWORKS_DATABASE_URL": "sqlite://",
        "JHWORKS_SESSION_COOKIE_NAME": "__session",
        "JHWORKS_COOKIE_SECURE": "true",
        "JHWORKS_FRONTEND_ORIGIN": "https://groupware.pikan.dev",
        "JHWORKS_JWT_SECRET": "synthetic-gateway-test-key-never-deploy",
        "JHWORKS_AI_ENABLED": "false",
        "JHWORKS_OPENAI_API_KEY": "",
    }
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "tests.firebase_cookie_scenario"],
        cwd=Path(__file__).parents[1], env=environment, capture_output=True,
        text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "firebase-cookie-scenario: passed"


def test_unhandled_error_is_not_cached_or_disclosed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(request: Request) -> Response:
        raise RuntimeError("synthetic-private-error-detail")

    # The production router is restored after the synthetic failure case.
    monkeypatch.setattr(app.router, "routes", [
        *app.router.routes, Route("/api/v1/_cache_failure", fail),
    ])
    with TestClient(app, raise_server_exceptions=False) as error_client:
        response = error_client.get("/api/v1/_cache_failure")
    assert response.status_code == 500
    assert "no-store" in response.headers.get("Cache-Control", "")
    assert "synthetic-private-error-detail" not in response.text

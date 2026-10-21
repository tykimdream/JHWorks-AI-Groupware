from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core.config import Settings, get_settings
from app.core.csrf import has_trusted_write_origin


@pytest.mark.parametrize(
    ("headers", "environment", "expected"),
    [
        ({"origin": "https://groupware.example.com"}, "production", True),
        ({"origin": "https://groupware.example.com:443"}, "production", True),
        ({"origin": "https://GROUPWARE.example.com"}, "production", True),
        ({"referer": "https://groupware.example.com/approvals?tab=mine"}, "prod", True),
        ({}, "development", True),
        ({}, "production", False),
        ({}, "prod", False),
        ({"origin": "null"}, "development", False),
        ({"origin": ""}, "development", False),
        ({"origin": "https://evil.example.com"}, "development", False),
        ({"origin": "https://groupware.example.com.evil.test"}, "production", False),
        ({"origin": "https://groupware.example.com:444"}, "production", False),
        ({"origin": "http://groupware.example.com"}, "production", False),
        ({"origin": "https://groupware.example.com/path"}, "production", False),
        ({"origin": "https://groupware.example.com?x=1"}, "production", False),
        ({"origin": "https://groupware.example.com#fragment"}, "production", False),
        ({"origin": "https://user@groupware.example.com"}, "production", False),
        ({"origin": "https://groupware.example.com:bad"}, "production", False),
        ({"origin": "https://groupware.example.com https://evil.test"}, "production", False),
        ({"origin": "https://groupware.example.com,https://evil.test"}, "production", False),
        ({"referer": "https://evil.test/approvals"}, "production", False),
        ({"referer": "null"}, "production", False),
        (
            {"origin": "null", "referer": "https://groupware.example.com/"},
            "production",
            False,
        ),
        (
            {"origin": "https://evil.test", "referer": "https://groupware.example.com/"},
            "production",
            False,
        ),
        ({"host": "groupware.example.com", "x-forwarded-host": "groupware.example.com"},
         "production", False),
    ],
)
def test_write_origin_policy(
    headers: dict[str, str], environment: str, expected: bool,
) -> None:
    # Construct development settings first; this test isolates the request policy,
    # not the independent production startup validation.
    settings = Settings(_env_file=None, frontend_origin="https://groupware.example.com")
    settings.environment = environment
    request = Request({
        "type": "http", "method": "POST", "path": "/api/v1/auth/login",
        "headers": [(key.encode(), value.encode()) for key, value in headers.items()],
    })
    assert has_trusted_write_origin(request, settings) is expected


@pytest.mark.parametrize(
    ("method", "expected"),
    [("GET", True), ("HEAD", True), ("OPTIONS", True), ("POST", False),
     ("PUT", False), ("PATCH", False), ("DELETE", False), ("TRACE", False)],
)
def test_method_policy(method: str, expected: bool) -> None:
    settings = Settings(_env_file=None)
    settings.environment = "production"
    request = Request({"type": "http", "method": method, "path": "/", "headers": []})
    assert has_trusted_write_origin(request, settings) is expected


@pytest.mark.parametrize("header", [b"origin", b"referer"])
def test_duplicate_source_headers_are_rejected(header: bytes) -> None:
    settings = Settings(_env_file=None)
    request = Request({
        "type": "http", "method": "POST", "path": "/",
        "headers": [(header, b"http://localhost:3000"), (header, b"http://localhost:3000")],
    })
    assert not has_trusted_write_origin(request, settings)


def test_cross_origin_login_is_rejected_before_cookie_creation(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "seojin.yoon@jhworks.test", "password": "demo1234"},
        headers={"Origin": "https://untrusted.example", "X-Request-ID": "csrf-test"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_ORIGIN_REJECTED"
    assert response.json()["requestId"] == response.headers["X-Request-ID"] == "csrf-test"
    assert "set-cookie" not in response.headers


def test_trusted_login_and_preflight_still_work(client: TestClient) -> None:
    origin = get_settings().frontend_origin
    preflight = client.options(
        "/api/v1/auth/login",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Origin"] == origin
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "seojin.yoon@jhworks.test", "password": "demo1234"},
        headers={"Origin": origin},
    )
    assert response.status_code == 200
    assert "jhworks_session" in response.cookies


def test_rejected_write_does_not_create_approval_or_logout(
    client: TestClient, login: Callable[[TestClient, str], None],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    before = client.get("/api/v1/approvals").json()
    response = client.post(
        "/api/v1/approvals",
        headers={"Origin": "https://untrusted.example"},
        json={"type": "GENERAL", "title": "CSRF synthetic draft", "content": "test",
              "details": {"kind": "GENERAL"}},
    )
    assert response.status_code == 403
    assert client.get("/api/v1/approvals").json() == before
    logout = client.post("/api/v1/auth/logout", headers={"Origin": "null"})
    assert logout.status_code == 403
    assert "set-cookie" not in logout.headers
    assert client.get("/api/v1/employees/me").status_code == 200


def test_production_requires_source_headers_but_keeps_reads(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "environment", "production")
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.get("/api/v1/health/live").status_code == 200
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Referer": f"{get_settings().frontend_origin}/approvals"},
    )
    assert response.status_code == 200

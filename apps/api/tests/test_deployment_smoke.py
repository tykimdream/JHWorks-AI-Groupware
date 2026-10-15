from collections.abc import Callable

from app.ops.deployment_smoke import HttpResult, run_smoke


def _successful_transport() -> Callable[[str, str, float], HttpResult]:
    def transport(url: str, request_id: str, _timeout: float) -> HttpResult:
        if url.endswith("/health/live"):
            body = b'{"status":"ok"}'
            status = 200
        elif url.endswith("/health/ready"):
            body = b'{"status":"ready","checks":{"database":"ok"}}'
            status = 200
        elif "/attendance/overview" in url:
            body = (
                '{"error":{"code":"AUTHENTICATION_REQUIRED"},'
                f'"requestId":"{request_id}"}}'
            ).encode()
            status = 401
        else:
            body = b"<html><title>JHWorks</title></html>"
            status = 200
        return HttpResult(
            status_code=status,
            headers={"x-request-id": request_id},
            body=body,
            latency_ms=4,
        )

    return transport


def test_deployment_smoke_verifies_all_public_boundaries() -> None:
    report = run_smoke(
        api_url="https://api.example.test/api/v1/",
        web_url="https://groupware.example.test/",
        timeout_seconds=1,
        attempts=1,
        retry_interval_seconds=0,
        transport=_successful_transport(),
    )

    assert report["status"] == "passed"
    assert report["summary"] == {"passed": 4, "total": 4}
    assert [check["name"] for check in report["checks"]] == [
        "api_liveness",
        "api_readiness",
        "unauthenticated_boundary",
        "web_root",
    ]


def test_deployment_smoke_retries_readiness_before_other_checks() -> None:
    calls = 0

    def transport(url: str, request_id: str, timeout: float) -> HttpResult:
        nonlocal calls
        if url.endswith("/health/ready"):
            calls += 1
            if calls == 1:
                return HttpResult(503, {"x-request-id": request_id}, b"{}", 3)
        return _successful_transport()(url, request_id, timeout)

    report = run_smoke(
        api_url="https://api.example.test/api/v1",
        web_url="https://groupware.example.test",
        timeout_seconds=1,
        attempts=2,
        retry_interval_seconds=0,
        transport=transport,
        sleep=lambda _: None,
    )

    assert calls == 2
    assert report["status"] == "passed"


def test_deployment_smoke_retries_transient_connection_failure() -> None:
    calls = 0

    def transport(url: str, request_id: str, timeout: float) -> HttpResult:
        nonlocal calls
        if url.endswith("/health/ready"):
            calls += 1
            if calls == 1:
                raise ConnectionResetError("database-password=secret")
        return _successful_transport()(url, request_id, timeout)

    report = run_smoke(
        api_url="https://api.example.test/api/v1",
        web_url="https://groupware.example.test",
        timeout_seconds=1,
        attempts=2,
        retry_interval_seconds=0,
        transport=transport,
        sleep=lambda _: None,
    )

    assert report["status"] == "passed"
    assert "database-password" not in str(report)


def test_deployment_smoke_retries_web_startup() -> None:
    web_calls = 0

    def transport(url: str, request_id: str, timeout: float) -> HttpResult:
        nonlocal web_calls
        if url == "https://groupware.example.test":
            web_calls += 1
            if web_calls == 1:
                raise ConnectionRefusedError("web is starting")
        return _successful_transport()(url, request_id, timeout)

    report = run_smoke(
        api_url="https://api.example.test/api/v1",
        web_url="https://groupware.example.test",
        timeout_seconds=1,
        attempts=2,
        retry_interval_seconds=0,
        transport=transport,
        sleep=lambda _: None,
    )

    assert web_calls == 2
    assert report["status"] == "passed"


def test_deployment_smoke_stops_when_database_is_not_ready() -> None:
    def transport(_url: str, request_id: str, _timeout: float) -> HttpResult:
        return HttpResult(503, {"x-request-id": request_id}, b"database-password=secret", 3)

    report = run_smoke(
        api_url="https://api.example.test/api/v1",
        web_url="https://groupware.example.test",
        timeout_seconds=1,
        attempts=1,
        retry_interval_seconds=0,
        transport=transport,
    )

    assert report["status"] == "failed"
    assert report["checks"][0]["result_code"] == "READINESS_CONTRACT_FAILED"
    assert "database-password" not in str(report)

import argparse
import json
import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

DEFAULT_OUTPUT_PATH = Path(__file__).parents[4] / "artifacts" / "smoke" / "latest.json"
MAX_RESPONSE_BYTES = 65_536


@dataclass(frozen=True)
class HttpResult:
    status_code: int
    headers: dict[str, str]
    body: bytes
    latency_ms: int


@dataclass(frozen=True)
class SmokeCheck:
    name: str
    passed: bool
    status_code: int | None
    latency_ms: int
    result_code: str


Transport = Callable[[str, str, float], HttpResult]


def _http_get(url: str, request_id: str, timeout_seconds: float) -> HttpResult:
    request = Request(
        url,
        headers={"Accept": "application/json", "X-Request-ID": request_id},
        method="GET",
    )
    started_at = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            return HttpResult(
                status_code=response.status,
                headers={key.lower(): value for key, value in response.headers.items()},
                body=response.read(MAX_RESPONSE_BYTES),
                latency_ms=round((time.perf_counter() - started_at) * 1000),
            )
    except HTTPError as exc:
        return HttpResult(
            status_code=exc.code,
            headers={key.lower(): value for key, value in exc.headers.items()},
            body=exc.read(MAX_RESPONSE_BYTES),
            latency_ms=round((time.perf_counter() - started_at) * 1000),
        )


def _json_body(result: HttpResult) -> dict[str, Any]:
    try:
        parsed = json.loads(result.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _request_id() -> str:
    return f"smoke-{uuid4().hex}"


def _run_check_safely(name: str, check: Callable[[], SmokeCheck]) -> SmokeCheck:
    try:
        return check()
    except (OSError, URLError) as exc:
        return SmokeCheck(
            name=name,
            passed=False,
            status_code=None,
            latency_ms=0,
            result_code=type(exc).__name__,
        )


def _retry_check(
    name: str,
    check: Callable[[], SmokeCheck],
    attempts: int,
    retry_interval_seconds: float,
    sleep: Callable[[float], None],
) -> SmokeCheck:
    result = _run_check_safely(name, check)
    for _ in range(attempts - 1):
        if result.passed:
            break
        sleep(retry_interval_seconds)
        result = _run_check_safely(name, check)
    return result


def _check_api_liveness(
    api_url: str,
    timeout_seconds: float,
    transport: Transport,
) -> SmokeCheck:
    request_id = _request_id()
    result = transport(f"{api_url}/health/live", request_id, timeout_seconds)
    body = _json_body(result)
    passed = (
        result.status_code == 200
        and body.get("status") == "ok"
        and result.headers.get("x-request-id") == request_id
    )
    return SmokeCheck(
        name="api_liveness",
        passed=passed,
        status_code=result.status_code,
        latency_ms=result.latency_ms,
        result_code="OK" if passed else "LIVENESS_CONTRACT_FAILED",
    )


def _check_api_readiness(
    api_url: str,
    timeout_seconds: float,
    transport: Transport,
) -> SmokeCheck:
    request_id = _request_id()
    result = transport(f"{api_url}/health/ready", request_id, timeout_seconds)
    body = _json_body(result)
    checks = body.get("checks")
    passed = (
        result.status_code == 200
        and body.get("status") == "ready"
        and isinstance(checks, dict)
        and checks.get("database") == "ok"
        and result.headers.get("x-request-id") == request_id
    )
    return SmokeCheck(
        name="api_readiness",
        passed=passed,
        status_code=result.status_code,
        latency_ms=result.latency_ms,
        result_code="OK" if passed else "READINESS_CONTRACT_FAILED",
    )


def _check_unauthenticated_boundary(
    api_url: str,
    timeout_seconds: float,
    transport: Transport,
) -> SmokeCheck:
    request_id = _request_id()
    path = "/attendance/overview?startDate=2026-09-01&endDate=2026-09-30"
    result = transport(f"{api_url}{path}", request_id, timeout_seconds)
    body = _json_body(result)
    error = body.get("error")
    passed = (
        result.status_code == 401
        and isinstance(error, dict)
        and error.get("code") == "AUTHENTICATION_REQUIRED"
        and body.get("requestId") == request_id
        and result.headers.get("x-request-id") == request_id
    )
    return SmokeCheck(
        name="unauthenticated_boundary",
        passed=passed,
        status_code=result.status_code,
        latency_ms=result.latency_ms,
        result_code="OK" if passed else "AUTH_BOUNDARY_FAILED",
    )


def _check_web_root(
    web_url: str,
    timeout_seconds: float,
    transport: Transport,
) -> SmokeCheck:
    result = transport(web_url, _request_id(), timeout_seconds)
    passed = result.status_code == 200 and b"JHWorks" in result.body
    return SmokeCheck(
        name="web_root",
        passed=passed,
        status_code=result.status_code,
        latency_ms=result.latency_ms,
        result_code="OK" if passed else "WEB_ROOT_FAILED",
    )


def run_smoke(
    api_url: str,
    web_url: str,
    timeout_seconds: float,
    attempts: int,
    retry_interval_seconds: float,
    transport: Transport = _http_get,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    normalized_api_url = api_url.rstrip("/")
    normalized_web_url = web_url.rstrip("/") or web_url
    readiness = _retry_check(
        "api_readiness",
        lambda: _check_api_readiness(normalized_api_url, timeout_seconds, transport),
        attempts,
        retry_interval_seconds,
        sleep,
    )

    checks: list[SmokeCheck] = [readiness]
    if readiness.passed:
        checks = [
            _run_check_safely(
                "api_liveness",
                lambda: _check_api_liveness(
                    normalized_api_url,
                    timeout_seconds,
                    transport,
                ),
            ),
            readiness,
            _run_check_safely(
                "unauthenticated_boundary",
                lambda: _check_unauthenticated_boundary(
                    normalized_api_url,
                    timeout_seconds,
                    transport,
                ),
            ),
            _retry_check(
                "web_root",
                lambda: _check_web_root(
                    normalized_web_url,
                    timeout_seconds,
                    transport,
                ),
                attempts,
                retry_interval_seconds,
                sleep,
            ),
        ]
    passed_count = sum(check.passed for check in checks)
    return {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(UTC).isoformat(),
        "status": "passed" if passed_count == len(checks) else "failed",
        "summary": {"passed": passed_count, "total": len(checks)},
        "checks": [asdict(check) for check in checks],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the deployed JHWorks API, DB boundary, auth boundary, and web root."
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("JHWORKS_SMOKE_API_URL", "http://localhost:8000/api/v1"),
    )
    parser.add_argument(
        "--web-url",
        default=os.getenv("JHWORKS_SMOKE_WEB_URL", "http://localhost:3000"),
    )
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--attempts", type=int, default=15)
    parser.add_argument("--retry-interval-seconds", type=float, default=2.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.timeout_seconds <= 0 or args.attempts < 1 or args.retry_interval_seconds < 0:
        raise SystemExit("Timeout and attempts must be positive")
    try:
        report = run_smoke(
            api_url=args.api_url,
            web_url=args.web_url,
            timeout_seconds=args.timeout_seconds,
            attempts=args.attempts,
            retry_interval_seconds=args.retry_interval_seconds,
        )
    except (OSError, URLError) as exc:
        report = {
            "schemaVersion": "1.0",
            "generatedAt": datetime.now(UTC).isoformat(),
            "status": "unavailable",
            "summary": {"passed": 0, "total": 1},
            "checks": [
                {
                    "name": "deployment_connection",
                    "passed": False,
                    "status_code": None,
                    "latency_ms": 0,
                    "result_code": type(exc).__name__,
                }
            ],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    args.output.write_text(serialized)
    print(serialized, end="")
    if report["status"] == "unavailable":
        return 2
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

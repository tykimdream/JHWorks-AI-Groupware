import json
import logging
import sys
from collections.abc import Generator
from typing import cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db
from app.core.logging import JsonFormatter
from app.main import app


def test_json_exception_log_omits_vendor_message() -> None:
    try:
        raise RuntimeError("database-password=secret")
    except RuntimeError:
        record = logging.LogRecord(
            name="jhworks.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="operation_failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["exception"]["type"] == "RuntimeError"
    assert "database-password" not in json.dumps(payload)


def test_request_id_is_preserved_and_returned_on_errors(client: TestClient) -> None:
    response = client.get(
        "/api/v1/attendance/overview?startDate=2026-09-01&endDate=2026-09-30",
        headers={"X-Request-ID": "web-trace-123"},
    )

    assert response.status_code == 401
    assert response.headers["X-Request-ID"] == "web-trace-123"
    assert response.json()["requestId"] == "web-trace-123"


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get(
        "/api/v1/health/live",
        headers={"X-Request-ID": "invalid\nlog-entry"},
    )

    assert response.status_code == 200
    UUID(response.headers["X-Request-ID"])


def test_readiness_checks_database(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


def test_readiness_failure_does_not_expose_database_details(client: TestClient) -> None:
    class FailingSession:
        def execute(self, _statement: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("database secret"))

    def override_get_db() -> Generator[Session, None, None]:
        yield cast(Session, FailingSession())

    app.dependency_overrides[get_db] = override_get_db
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "READINESS_CHECK_FAILED",
        "message": "The service is not ready to accept traffic.",
        "details": None,
    }
    assert "database secret" not in response.text


def test_production_settings_require_secure_persistent_configuration() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, environment="production")

    message = str(exc_info.value)
    assert "JHWORKS_JWT_SECRET" in message
    assert "JHWORKS_COOKIE_SECURE" in message
    assert "JHWORKS_DATABASE_URL" in message
    assert "JHWORKS_FRONTEND_ORIGIN" in message


def test_secure_production_settings_are_valid() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret="a-secure-production-secret-value-123456",
        cookie_secure=True,
        database_url="postgresql+psycopg://jhworks:secret@db.example/jhworks",
        frontend_origin="https://groupware.example.com",
    )

    assert settings.environment == "production"

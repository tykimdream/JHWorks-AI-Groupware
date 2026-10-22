from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import (
    create_session_token,
    decode_approval_draft_confirmation_token,
    decode_leave_draft_confirmation_token,
    decode_leave_submit_confirmation_token,
    decode_session_token,
)

DECODERS: list[Callable[[str], object]] = [
    decode_session_token,
    decode_approval_draft_confirmation_token,
    decode_leave_draft_confirmation_token,
    decode_leave_submit_confirmation_token,
]
TOKEN_TYPES = [
    "session",
    "approval_draft_confirmation",
    "leave_draft_confirmation",
    "leave_submit_confirmation",
]


def _payload(token_type: str) -> dict[str, Any]:
    now = int(datetime.now(UTC).timestamp())
    return {
        "sub": "emp_sales_001",
        "iat": now,
        "exp": now + 300,
        "type": token_type,
        "jti": "test_confirmation",
        "preview_hash": "test_preview",
        "candidate_hash": "test_candidate",
        "account_version": 1,
        "calendar_fingerprint": "test_calendar",
        "manager_id": "emp_sales_mgr_001",
        "policy_fingerprint": "test_policy",
        "run_id": "test_run",
        "approval_id": "test_approval",
        "approval_version": 1,
    }


def _encode(payload: dict[str, Any]) -> str:
    settings = get_settings()
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.mark.parametrize(("decoder", "token_type"), list(zip(DECODERS, TOKEN_TYPES, strict=True)))
@pytest.mark.parametrize("missing", ["sub", "type", "exp", "iat"])
def test_signed_token_requires_time_claims(
    decoder: Callable[[str], object],
    token_type: str,
    missing: str,
) -> None:
    payload = _payload(token_type)
    del payload[missing]
    with pytest.raises((AuthenticationError, ConflictError)):
        decoder(_encode(payload))


@pytest.mark.parametrize(("decoder", "token_type"), list(zip(DECODERS, TOKEN_TYPES, strict=True)))
@pytest.mark.parametrize(
    "invalid", ["expired", "future", "reversed", "string", "boolean", "list", "infinite"]
)
def test_signed_token_rejects_invalid_lifetime(
    decoder: Callable[[str], object],
    token_type: str,
    invalid: str,
) -> None:
    payload = _payload(token_type)
    now = int(datetime.now(UTC).timestamp())
    if invalid == "expired":
        payload.update(iat=now - 300, exp=now - 1)
    elif invalid == "future":
        payload.update(iat=now + 300, exp=now + 600)
    elif invalid == "reversed":
        payload.update(iat=now, exp=now)
    elif invalid == "string":
        payload["exp"] = str(now + 300)
    elif invalid == "boolean":
        payload["iat"] = True
    elif invalid == "list":
        payload["iat"] = []
    else:
        payload["exp"] = float("inf")
    with pytest.raises((AuthenticationError, ConflictError)):
        decoder(_encode(payload))


@pytest.mark.parametrize(("decoder", "token_type"), list(zip(DECODERS, TOKEN_TYPES, strict=True)))
def test_valid_signed_token_keeps_its_contract(
    decoder: Callable[[str], object],
    token_type: str,
) -> None:
    assert decoder(_encode(_payload(token_type))) is not None


def test_generated_session_obeys_configured_lifetime() -> None:
    settings = get_settings()
    token = create_session_token("emp_sales_001")
    assert decode_session_token(token) == "emp_sales_001"
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert payload["exp"] - payload["iat"] == settings.session_ttl_minutes * 60


@pytest.mark.parametrize("invalid", ["expired", "missing_exp", "wrong_type", "empty_subject"])
def test_invalid_session_cannot_read_or_write(client: TestClient, invalid: str) -> None:
    payload = _payload("session")
    if invalid == "expired":
        payload["exp"] = int((datetime.now(UTC) - timedelta(seconds=1)).timestamp())
    elif invalid == "missing_exp":
        del payload["exp"]
    elif invalid == "wrong_type":
        payload["type"] = "approval_draft_confirmation"
    else:
        payload["sub"] = ""
    client.cookies.set(get_settings().session_cookie_name, _encode(payload))
    for method, path, body in [
        ("GET", "/api/v1/employees/me", None),
        (
            "POST",
            "/api/v1/approvals",
            {"type": "GENERAL", "title": "Blocked", "content": "Blocked"},
        ),
    ]:
        response = client.request(method, path, json=body)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
        assert "no-store" in response.headers["cache-control"]
        assert "set-cookie" not in response.headers


@pytest.mark.parametrize(
    ("decoder", "expected_type"), list(zip(DECODERS, TOKEN_TYPES, strict=True))
)
@pytest.mark.parametrize("received_type", TOKEN_TYPES)
def test_token_purpose_cannot_be_replayed(
    decoder: Callable[[str], object],
    expected_type: str,
    received_type: str,
) -> None:
    token = _encode(_payload(received_type))
    if received_type == expected_type:
        assert decoder(token) is not None
    else:
        with pytest.raises((AuthenticationError, ConflictError)):
            decoder(token)

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.errors import AuthenticationError, ConflictError

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_session_token(employee_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": employee_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.session_ttl_minutes),
        "type": "session",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> str:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise AuthenticationError("The session is invalid or expired") from exc

    employee_id = payload.get("sub")
    if not isinstance(employee_id, str) or payload.get("type") != "session":
        raise AuthenticationError("The session is invalid")
    return employee_id


@dataclass(frozen=True)
class ApprovalDraftConfirmation:
    employee_id: str
    confirmation_id: str
    preview_hash: str


@dataclass(frozen=True)
class LeaveDraftConfirmation:
    employee_id: str
    confirmation_id: str
    preview_hash: str
    candidate_hash: str
    account_version: int
    calendar_fingerprint: str
    manager_id: str
    policy_fingerprint: str


def create_approval_draft_confirmation_token(
    employee_id: str,
    confirmation_id: str,
    preview_hash: str,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": employee_id,
        "jti": confirmation_id,
        "preview_hash": preview_hash,
        "iat": now,
        "exp": now + timedelta(minutes=settings.approval_draft_confirmation_ttl_minutes),
        "type": "approval_draft_confirmation",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_approval_draft_confirmation_token(token: str) -> ApprovalDraftConfirmation:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise ConflictError(
            "INVALID_CONFIRMATION",
            "The approval draft confirmation is invalid or expired.",
        ) from exc

    employee_id = payload.get("sub")
    confirmation_id = payload.get("jti")
    preview_hash = payload.get("preview_hash")
    if (
        payload.get("type") != "approval_draft_confirmation"
        or not isinstance(employee_id, str)
        or not isinstance(confirmation_id, str)
        or not isinstance(preview_hash, str)
    ):
        raise ConflictError(
            "INVALID_CONFIRMATION",
            "The approval draft confirmation is invalid.",
        )
    return ApprovalDraftConfirmation(
        employee_id=employee_id,
        confirmation_id=confirmation_id,
        preview_hash=preview_hash,
    )


def create_leave_draft_confirmation_token(
    employee_id: str,
    confirmation_id: str,
    preview_hash: str,
    candidate_hash: str,
    account_version: int,
    calendar_fingerprint: str,
    manager_id: str,
    policy_fingerprint: str,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": employee_id,
        "jti": confirmation_id,
        "preview_hash": preview_hash,
        "candidate_hash": candidate_hash,
        "account_version": account_version,
        "calendar_fingerprint": calendar_fingerprint,
        "manager_id": manager_id,
        "policy_fingerprint": policy_fingerprint,
        "iat": now,
        "exp": now + timedelta(minutes=settings.leave_draft_confirmation_ttl_minutes),
        "type": "leave_draft_confirmation",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_leave_draft_confirmation_token(token: str) -> LeaveDraftConfirmation:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise ConflictError(
            "INVALID_LEAVE_CONFIRMATION",
            "The leave draft confirmation is invalid or expired.",
        ) from exc

    required_strings = (
        "sub",
        "jti",
        "preview_hash",
        "candidate_hash",
        "calendar_fingerprint",
        "manager_id",
        "policy_fingerprint",
    )
    if (
        payload.get("type") != "leave_draft_confirmation"
        or not all(isinstance(payload.get(key), str) for key in required_strings)
        or not isinstance(payload.get("account_version"), int)
    ):
        raise ConflictError(
            "INVALID_LEAVE_CONFIRMATION",
            "The leave draft confirmation is invalid.",
        )
    return LeaveDraftConfirmation(
        employee_id=payload["sub"],
        confirmation_id=payload["jti"],
        preview_hash=payload["preview_hash"],
        candidate_hash=payload["candidate_hash"],
        account_version=payload["account_version"],
        calendar_fingerprint=payload["calendar_fingerprint"],
        manager_id=payload["manager_id"],
        policy_fingerprint=payload["policy_fingerprint"],
    )

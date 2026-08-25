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

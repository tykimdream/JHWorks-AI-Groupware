from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import DbSession
from app.core.errors import ServiceUnavailableError

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(db: DbSession) -> dict[str, str | dict[str, str]]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise ServiceUnavailableError(
            "READINESS_CHECK_FAILED",
            "The service is not ready to accept traffic.",
        ) from exc
    return {"status": "ready", "checks": {"database": "ok"}}

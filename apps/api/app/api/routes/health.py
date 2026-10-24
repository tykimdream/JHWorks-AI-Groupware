from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import DbSession
from app.core.errors import ServiceUnavailableError

router = APIRouter(tags=["운영"])


@router.get("/health", summary="서비스 상태 확인")
def health() -> dict[str, str]:
    """
    기본 상태 응답을 반환합니다. DB 연결 확인은 readiness
    API를 사용합니다.
    """
    return {"status": "ok"}


@router.get("/health/live", summary="프로세스 상태 확인")
def liveness() -> dict[str, str]:
    """API 프로세스가 응답하는지 확인합니다. DB 상태는 검사하지 않습니다."""
    return {"status": "ok"}


@router.get("/health/ready", summary="DB 연결 상태 확인")
def readiness(db: DbSession) -> dict[str, str | dict[str, str]]:
    """API가 DB에 연결해 요청을 처리할 준비가 되었는지 확인합니다."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise ServiceUnavailableError(
            "READINESS_CHECK_FAILED",
            "The service is not ready to accept traffic.",
        ) from exc
    return {"status": "ready", "checks": {"database": "ok"}}

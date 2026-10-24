from fastapi import APIRouter

from app.api.dependencies import DbSession, FeedbackEmployee
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.schemas.demo_feedback import DemoFeedbackCreate, DemoFeedbackReceipt
from app.services.demo_feedback import submit_feedback

router = APIRouter(prefix="/demo", tags=["인증·체험"])


@router.post("/feedback", response_model=DemoFeedbackReceipt, summary="체험 의견 접수")
def feedback(
    payload: DemoFeedbackCreate, db: DbSession, actor: FeedbackEmployee
) -> DemoFeedbackReceipt:
    """
    동의를 받은 체험 의견을 접수하고 접수번호를 반환합니다. 접수된
    의견을 공개 조회하는 API는 제공하지 않습니다.
    """
    if not get_settings().public_demo_enabled:
        raise NotFoundError("Demo feedback")
    return submit_feedback(db, actor, payload)

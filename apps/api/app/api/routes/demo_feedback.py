from fastapi import APIRouter

from app.api.dependencies import DbSession, FeedbackEmployee
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.schemas.demo_feedback import DemoFeedbackCreate, DemoFeedbackReceipt
from app.services.demo_feedback import submit_feedback

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/feedback", response_model=DemoFeedbackReceipt)
def feedback(
    payload: DemoFeedbackCreate, db: DbSession, actor: FeedbackEmployee
) -> DemoFeedbackReceipt:
    if not get_settings().public_demo_enabled:
        raise NotFoundError("Demo feedback")
    return submit_feedback(db, actor, payload)

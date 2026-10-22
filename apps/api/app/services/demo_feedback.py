import hashlib
import json
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import AppError, AuthenticationError, ConflictError, ServiceUnavailableError
from app.models.demo_feedback import DemoFeedback, DemoFeedbackGate
from app.models.employee import Employee
from app.schemas.demo_feedback import DemoFeedbackCreate, DemoFeedbackReceipt
from app.services.login_budget import database_seconds

MAX_FEEDBACK = 300
RETENTION_SECONDS = 30 * 86400


def submit_feedback(
    db: Session, actor: Employee, payload: DemoFeedbackCreate
) -> DemoFeedbackReceipt:
    if actor.demo_workspace_id is None:
        raise AuthenticationError()
    if db.new or db.dirty or db.deleted:
        raise ValueError("Feedback admission must precede changes")
    workspace_hash = hashlib.sha256(actor.demo_workspace_id.encode()).hexdigest()
    content_hash = hashlib.sha256(
        json.dumps(
            payload.model_dump(),
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    try:
        insert = (
            pg_insert(DemoFeedbackGate)
            if db.get_bind().dialect.name == "postgresql"
            else sqlite_insert(DemoFeedbackGate)
        )
        # Serialize capacity and idempotency checks across all instances.
        db.execute(
            insert.values(id=1, revision=1).on_conflict_do_update(
                index_elements=["id"],
                set_={"revision": DemoFeedbackGate.revision + 1},
            )
        )
        existing = db.scalar(
            select(DemoFeedback).where(
                DemoFeedback.workspace_hash == workspace_hash,
            )
        )
        if existing is not None:
            if existing.content_hash != content_hash:
                db.rollback()
                raise ConflictError("DEMO_FEEDBACK_ALREADY_SENT", "Feedback was already received.")
            receipt = DemoFeedbackReceipt(id=existing.id)
            db.commit()
            return receipt
        if (db.scalar(select(func.count()).select_from(DemoFeedback)) or 0) >= MAX_FEEDBACK:
            db.rollback()
            raise AppError("DEMO_FEEDBACK_CAPACITY", "Feedback is temporarily unavailable.", 429)
        feedback = DemoFeedback(
            id="feedback_" + uuid4().hex,
            workspace_hash=workspace_hash,
            content_hash=content_hash,
            category=payload.category,
            screen=payload.screen,
            message=payload.message,
            created_at_epoch=database_seconds(db),
        )
        db.add(feedback)
        db.commit()
        return DemoFeedbackReceipt(id=feedback.id)
    except SQLAlchemyError:
        db.rollback()
        raise ServiceUnavailableError(
            "DEMO_FEEDBACK_UNAVAILABLE", "Feedback is temporarily unavailable."
        ) from None

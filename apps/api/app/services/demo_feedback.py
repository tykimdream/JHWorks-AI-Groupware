import hashlib
import json
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import delete, func, select
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


def _lock_gate(db: Session) -> None:
    insert = (
        pg_insert(DemoFeedbackGate)
        if db.get_bind().dialect.name == "postgresql"
        else sqlite_insert(DemoFeedbackGate)
    )
    db.execute(
        insert.values(id=1, revision=1).on_conflict_do_update(
            index_elements=["id"],
            set_={"revision": DemoFeedbackGate.revision + 1},
        )
    )


@dataclass(frozen=True)
class FeedbackRetentionResult:
    expired: int
    removed: int
    stored: int


def purge_expired_feedback(db: Session, *, apply: bool = False) -> FeedbackRetentionResult:
    """Use the admission lock so concurrent operators report actual deletions."""
    if db.new or db.dirty or db.deleted or db.in_transaction():
        raise ValueError("Feedback retention requires a fresh session")
    try:
        _lock_gate(db)
        cutoff = database_seconds(db) - RETENTION_SECONDS
        expired = (
            db.scalar(
                select(func.count())
                .select_from(DemoFeedback)
                .where(DemoFeedback.created_at_epoch <= cutoff)
            )
            or 0
        )
        removed = 0
        if apply:
            removed = len(
                list(
                    db.scalars(
                        delete(DemoFeedback)
                        .where(DemoFeedback.created_at_epoch <= cutoff)
                        .returning(DemoFeedback.id)
                    )
                )
            )
        stored = db.scalar(select(func.count()).select_from(DemoFeedback)) or 0
        result = FeedbackRetentionResult(expired=expired, removed=removed, stored=stored)
        if apply:
            db.commit()
        else:
            db.rollback()
        return result
    except Exception:
        db.rollback()
        raise


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
        # Serialize capacity and idempotency checks across all instances.
        _lock_gate(db)
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

"""Shared, fail-closed reservations. Never construct a provider or commit business sessions."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.ai_budget import AIBudgetLimits as AIBudgetLimits
from app.core.errors import AppError, ConflictError, ServiceUnavailableError
from app.models.ai_budget import AIBudgetCounter, AIBudgetReservation
from app.services.login_budget import database_seconds

GLOBAL_KEY = "global"


@dataclass(frozen=True)
class BudgetReceipt:
    id: str
    maximum_micro_usd: int
    status: str
    charged_micro_usd: int | None


class AIBudgetLimitError(AppError):
    def __init__(self, *, busy: bool = False) -> None:
        super().__init__(
            "AI_BUSY" if busy else "AI_BUDGET_EXHAUSTED",
            "AI is busy. Retry shortly or use manual entry."
            if busy
            else "AI budget is unavailable. Use manual entry.",
            429,
        )


def _fresh(db: Session) -> None:
    if db.new or db.dirty or db.deleted or db.in_transaction():
        raise ValueError("AI budget requires a separate fresh session, not a business transaction")


def _keys(workspace_id: str, epoch: int) -> tuple[str, str, str]:
    now = datetime.fromtimestamp(epoch, UTC).astimezone(ZoneInfo("Asia/Seoul"))
    opaque = hashlib.sha256(("demo-ai:" + workspace_id).encode()).hexdigest()
    return f"day:{now:%Y-%m-%d}", f"month:{now:%Y-%m}", f"workspace:{opaque}:{now:%Y-%m-%d}"


def _lock_counters(db: Session, keys: tuple[str, ...]) -> dict[str, AIBudgetCounter]:
    dialect = db.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise ValueError("Unsupported AI budget database")
    insert = (
        pg_insert(AIBudgetCounter) if dialect == "postgresql" else sqlite_insert(AIBudgetCounter)
    )
    # Lock the timeless global row first, including when day/month boundaries differ.
    # SQLite obtains its writer lock at the first insert; PostgreSQL locks each selected row.
    rows: dict[str, AIBudgetCounter] = {}
    for key in sorted(keys, key=lambda value: (value != GLOBAL_KEY, value)):
        db.execute(
            insert.values(
                key=key,
                reserved_micro_usd=0,
                spent_micro_usd=0,
                admissions=0,
                active_requests=0,
                last_observed_epoch=0,
                is_frozen=False,
            ).on_conflict_do_nothing(index_elements=["key"])
        )
        row = db.scalar(select(AIBudgetCounter).where(AIBudgetCounter.key == key).with_for_update())
        if row is None:
            raise SQLAlchemyError("AI budget counter unavailable")
        rows[key] = row
    return rows


def _receipt(row: AIBudgetReservation) -> BudgetReceipt:
    return BudgetReceipt(row.id, row.maximum_micro_usd, row.status, row.charged_micro_usd)


def reserve(
    db: Session,
    *,
    workspace_id: str,
    maximum_micro_usd: int,
    limits: AIBudgetLimits,
) -> BudgetReceipt:
    """Commit worst-case cost before calling a provider; workspace comes from server identity.

    This is admission, not evidence that a provider was called. Role changes share the workspace.
    No public route uses this foundation yet. Callers must bound every paid stage/retry in maximum.
    """
    _fresh(db)
    if not workspace_id.strip() or len(workspace_id) > 64:
        raise ValueError("Expected an opaque server workspace ID")
    if type(maximum_micro_usd) is not int or not 1 <= maximum_micro_usd <= 10**12:
        raise ValueError("Expected a positive integer worst-case cost")
    try:
        global_counter = _lock_counters(db, (GLOBAL_KEY,))[GLOBAL_KEY]
        # Read shared DB time only after waiting for the admission lock.
        epoch = database_seconds(db)
        if epoch < global_counter.last_observed_epoch:
            raise ServiceUnavailableError(
                "AI_BUDGET_CLOCK_REVERSED", "AI is paused. Use manual entry."
            )
        day, month, scope = _keys(workspace_id, epoch)
        counters = _lock_counters(db, (day, month, scope))
        if global_counter.is_frozen:
            raise ServiceUnavailableError("AI_BUDGET_FROZEN", "AI is paused. Use manual entry.")
        if global_counter.active_requests >= limits.concurrent_requests:
            raise AIBudgetLimitError(busy=True)
        if (
            counters[day].admissions >= limits.day_admissions
            or counters[scope].admissions >= limits.scope_day_admissions
            or counters[day].spent_micro_usd + counters[day].reserved_micro_usd + maximum_micro_usd
            > limits.day_micro_usd
            or counters[month].spent_micro_usd
            + counters[month].reserved_micro_usd
            + maximum_micro_usd
            > limits.month_micro_usd
        ):
            raise AIBudgetLimitError()
        for key in (day, month, scope):
            counters[key].reserved_micro_usd += maximum_micro_usd
            counters[key].admissions += 1
        global_counter.active_requests += 1
        global_counter.last_observed_epoch = epoch
        row = AIBudgetReservation(
            id="air_" + uuid4().hex,
            day_key=day,
            month_key=month,
            scope_key=scope,
            maximum_micro_usd=maximum_micro_usd,
            created_at_epoch=epoch,
            status="RESERVED",
        )
        db.add(row)
        result = _receipt(row)
        db.commit()
        return result
    except AppError:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise ServiceUnavailableError(
            "AI_BUDGET_UNAVAILABLE", "AI is unavailable. Use manual entry."
        ) from None


def settle(
    db: Session, reservation_id: str, *, actual_micro_usd: int | None, freeze: bool = False
) -> BudgetReceipt:
    """Settle trusted server usage; unknown billing consumes the full reservation.

    An overrun records the real charge and freezes all new admissions. A process crash leaves
    its reservation and slot held, fail-closed; no automatic lease expiry/refund is provided.
    Do not expose this operation as a client-supplied usage or refund API.
    """
    _fresh(db)
    if actual_micro_usd is not None and (
        type(actual_micro_usd) is not int or not 0 <= actual_micro_usd <= 10**12
    ):
        raise ValueError("Expected trusted non-negative integer usage or unknown")
    try:
        row = db.get(AIBudgetReservation, reservation_id)
        if row is None:
            raise ConflictError("AI_RESERVATION_NOT_FOUND", "Unknown AI reservation")
        counters = _lock_counters(db, (GLOBAL_KEY, row.day_key, row.month_key, row.scope_key))
        row = db.scalar(
            select(AIBudgetReservation)
            .where(AIBudgetReservation.id == reservation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise ConflictError("AI_RESERVATION_NOT_FOUND", "Unknown AI reservation")
        charged = row.maximum_micro_usd if actual_micro_usd is None else actual_micro_usd
        status = (
            "UNCERTAIN"
            if actual_micro_usd is None
            else "OVERRUN"
            if charged > row.maximum_micro_usd
            else "SETTLED"
        )
        if freeze:
            counters[GLOBAL_KEY].is_frozen = True
        if row.status != "RESERVED":
            if row.status != status or row.charged_micro_usd != charged:
                raise ConflictError("AI_SETTLEMENT_CHANGED", "AI settlement cannot be overwritten")
            result = _receipt(row)
            db.commit()
            return result
        for key in (row.day_key, row.month_key, row.scope_key):
            counters[key].reserved_micro_usd -= row.maximum_micro_usd
            counters[key].spent_micro_usd += charged
        counters[GLOBAL_KEY].active_requests -= 1
        if status == "OVERRUN":
            counters[GLOBAL_KEY].is_frozen = True
        row.status, row.charged_micro_usd = status, charged
        result = _receipt(row)
        db.commit()
        return result
    except AppError:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise ServiceUnavailableError(
            "AI_BUDGET_UNAVAILABLE", "AI is unavailable. Use manual entry."
        ) from None

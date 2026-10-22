"""A shared fixed-minute budget for expensive password verification."""

from sqlalchemy import BigInteger, and_, case, cast, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import RateLimitError, ServiceUnavailableError
from app.models.login_budget import LoginBudget


def database_seconds(db: Session) -> int:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        # Database time is shared by all replicas; do not trust proxy headers or host clocks.
        value = db.scalar(select(func.floor(func.extract("epoch", func.clock_timestamp()))))
    elif dialect == "sqlite":
        value = db.scalar(select(cast(func.strftime("%s", "now"), BigInteger)))
    else:
        raise ValueError("Unsupported login budget database")
    if value is None:
        raise SQLAlchemyError("Database clock unavailable")
    return int(value)


def reserve_login_attempt(db: Session, limit: int) -> None:
    """Commit a quota reservation before authentication, including failed logins.

    Call only at the start of the login route, before any business reads/writes.
    This intentionally commits its counter even when later authentication fails.
    """
    if not 1 <= limit <= 600:
        raise ValueError("Login budget must be between 1 and 600")
    if db.new or db.dirty or db.deleted or db.in_transaction():
        raise ValueError("Login budget requires a fresh request session")
    try:
        window = database_seconds(db) // 60
        dialect = db.get_bind().dialect.name
        insert = pg_insert(LoginBudget) if dialect == "postgresql" else sqlite_insert(LoginBudget)
        newer_window = LoginBudget.window < window
        statement = (
            insert.values(id=1, window=window, attempts=1)
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "window": case((newer_window, window), else_=LoginBudget.window),
                    "attempts": case((newer_window, 1), else_=LoginBudget.attempts + 1),
                },
                where=or_(
                    newer_window,
                    and_(LoginBudget.window == window, LoginBudget.attempts < limit),
                ),
            )
            .returning(LoginBudget.id)
        )
        admitted = db.scalar(statement) is not None
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise ServiceUnavailableError(
            "LOGIN_BUDGET_UNAVAILABLE", "Login is temporarily unavailable. Please try again."
        ) from None
    if not admitted:
        raise RateLimitError()

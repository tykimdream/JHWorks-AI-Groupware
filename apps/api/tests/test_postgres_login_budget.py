"""Real local PostgreSQL concurrency; no staging or remote DB access."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import RateLimitError
from app.models.login_budget import LoginBudget
from app.services import login_budget
from tests.test_postgres_approval_lists import session_factory as session_factory


@pytest.mark.parametrize("existing", [False, True])
def test_shared_budget_cannot_over_admit(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    existing: bool,
) -> None:
    monkeypatch.setattr(login_budget, "database_seconds", lambda db: 120)
    if existing:
        with session_factory() as db:
            login_budget.reserve_login_attempt(db, 5)
    barrier = Barrier(8)

    def attempt(_: int) -> bool:
        barrier.wait(timeout=20)
        with session_factory() as db:
            try:
                login_budget.reserve_login_attempt(db, 5)
                return True
            except RateLimitError:
                return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        admitted = sum(executor.map(attempt, range(24)))
    assert admitted == (4 if existing else 5)
    with session_factory() as db:
        row = db.get(LoginBudget, 1)
        assert row is not None and row.attempts == 5


def test_postgres_clock(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        assert login_budget.database_seconds(db) > 0

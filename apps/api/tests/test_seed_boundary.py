from typing import Any, NoReturn

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.scripts.seed import seed_database


@pytest.mark.parametrize(
    ("environment", "database_url"),
    [
        ("production", "sqlite://"),
        ("staging", "sqlite://"),
        ("preview", "sqlite://"),
        ("development", "postgresql+psycopg://synthetic:unused@foreign.test/postgres"),
        ("test", "postgresql+psycopg://synthetic:unused@aws-0-ap-northeast-2.pooler.supabase.com/postgres"),
    ],
)
def test_public_seed_rejects_hosted_or_nonlocal_environments_before_connecting(
    environment: str, database_url: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "environment", environment)
    engine = create_engine(database_url)

    def unexpected_connection(*args: Any, **kwargs: Any) -> NoReturn:
        raise AssertionError("Seed must reject this target before opening a connection")

    event.listen(engine, "do_connect", unexpected_connection)
    try:
        with Session(engine) as db, pytest.raises(RuntimeError, match="restricted to local"):
            seed_database(db)
    finally:
        engine.dispose()

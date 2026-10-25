"""Rehearse AI accounting migration in a disposable SQLite database."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


def test_budget_migration_preserves_existing_rows_and_refuses_ledger_reset(tmp_path: Path) -> None:
    url = "sqlite:///" + (tmp_path / "migration.db").as_posix()
    env = {**os.environ, "JHWORKS_DATABASE_URL": url, "JHWORKS_ENVIRONMENT": "test"}

    def migrate(*args: str, success: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=Path(__file__).parents[1],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert (result.returncode == 0) == success, result.stderr
        return result

    migrate("upgrade", "f30c9a71b624")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO departments (id,name,is_active) "
                    "VALUES ('private_dept','Synthetic',1)"
                )
            )
        migrate("upgrade", "head")
        assert "ai_budget_reservations" in inspect(engine).get_table_names()
        migrate("downgrade", "f30c9a71b624")
        assert "ai_budget_counters" not in inspect(engine).get_table_names()
        migrate("upgrade", "head")
        with engine.begin() as connection:
            assert (
                connection.execute(
                    text("SELECT name FROM departments WHERE id='private_dept'")
                ).scalar_one()
                == "Synthetic"
            )
            connection.execute(
                text(
                    "INSERT INTO ai_budget_counters "
                    "(key,reserved_micro_usd,spent_micro_usd,admissions,"
                    "active_requests,last_observed_epoch,is_frozen) "
                    "VALUES ('global',0,0,0,0,0,0)"
                )
            )
        refused = migrate("downgrade", "f30c9a71b624", success=False)
        assert "Cannot drop AI accounting" in refused.stderr
        assert "ai_budget_reservations" in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT count(*) FROM ai_budget_counters")).scalar_one()
                == 1
            )
    finally:
        engine.dispose()

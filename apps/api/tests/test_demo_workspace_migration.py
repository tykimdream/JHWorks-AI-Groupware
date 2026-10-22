"""Migration rehearsal in a disposable local SQLite file, never an external DB."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


def test_workspace_migration_preserves_private_identity_and_guards_downgrade(
    tmp_path: Path,
) -> None:
    url = "sqlite:///" + (tmp_path / "workspace_migration.db").as_posix()
    env = os.environ.copy()
    env["JHWORKS_DATABASE_URL"] = url
    env["JHWORKS_ENVIRONMENT"] = "test"
    env["PYTHONUTF8"] = "1"

    def migrate(*arguments: str, success: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *arguments],
            cwd=Path(__file__).parents[1],
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=60,
        )
        assert (result.returncode == 0) == success, result.stderr
        return result

    migrate("upgrade", "c84f2a19d6e0")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO departments (id,name,is_active) "
                    "VALUES ('private_dept','Synthetic',1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO employees "
                    "(id,name,email,department_id,position,role,hire_date,leave_balance,is_active) "
                    "VALUES ('private_actor','Synthetic','migration@jhworks.test','private_dept',"
                    "'Synthetic','EMPLOYEE','2026-01-01',5,1)"
                )
            )
            before = connection.execute(text("SELECT * FROM employees")).mappings().one()
            original = dict(before)
        migrate("upgrade", "head")
        with engine.connect() as connection:
            after = dict(connection.execute(text("SELECT * FROM employees")).mappings().one())
            assert after.pop("demo_workspace_id") is None
            assert after == original
        inspector = inspect(engine)
        assert any(
            item["name"] == "demo_workspace_id" and item["nullable"]
            for item in inspector.get_columns("employees")
        )
        assert any(
            item["name"] == "ix_employees_department_demo_workspace"
            for item in inspector.get_indexes("employees")
        )
        assert any(
            item["referred_table"] == "demo_workspaces"
            for item in inspector.get_foreign_keys("employees")
        )
        migrate("downgrade", "c84f2a19d6e0")
        with engine.connect() as connection:
            assert (
                dict(connection.execute(text("SELECT * FROM employees")).mappings().one())
                == original
            )
        migrate("upgrade", "head")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO demo_workspaces "
                    "(id,department_id,expires_at_epoch,is_active,write_limit,writes_used) "
                    "VALUES ('test_workspace','private_dept',2000000000,1,5,0)"
                )
            )
        refused = migrate("downgrade", "c84f2a19d6e0", success=False)
        assert "Cannot remove workspace protection" in refused.stderr
        assert "demo_workspace_id" in {
            item["name"] for item in inspect(engine).get_columns("employees")
        }
    finally:
        engine.dispose()

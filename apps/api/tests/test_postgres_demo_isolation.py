"""Real migration/grant checks; only disposable loopback PostgreSQL is allowed."""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.exc import DBAPIError

from alembic import command

ROOT = Path(__file__).resolve().parents[3]
SQL = (ROOT / "deploy/cloud-run/supabase-demo-bootstrap.sql").read_text(encoding="utf-8")


@pytest.fixture
def owner() -> Generator[Connection, None, None]:
    raw = os.environ.get("JHWORKS_TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("dedicated local PostgreSQL test URL not configured")
    url = make_url(raw)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.database != "jhworks_test"
        or url.username != "jhworks_test"
    ):
        pytest.fail("only the dedicated loopback jhworks_test database/user is allowed")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                # All fixture roles/schema/ACL/migrations roll back together. Never
                # drop or adopt pre-existing targets, even in the test database.
                for role in ("jhworks_demo_migrate", "jhworks_demo_runtime"):
                    assert not connection.scalar(
                        text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}
                    ), "dedicated test role already exists"
                for schema in ("groupware", "groupware_demo"):
                    assert not connection.scalar(
                        text("SELECT 1 FROM pg_namespace WHERE nspname=:schema"), {"schema": schema}
                    ), "dedicated test schema already exists"
                for role in ("anon", "authenticated", "postgres"):
                    if not connection.scalar(
                        text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}
                    ):
                        connection.exec_driver_sql(f"CREATE ROLE {role} NOLOGIN")
                connection.exec_driver_sql("CREATE SCHEMA groupware")
                connection.exec_driver_sql("REVOKE ALL ON SCHEMA groupware FROM PUBLIC")
                connection.exec_driver_sql("CREATE TABLE groupware.private_sentinel (value text)")
                connection.exec_driver_sql(
                    "INSERT INTO groupware.private_sentinel VALUES ('synthetic-private')"
                )
                connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS extensions")
                connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
                if connection.scalar(text(
                    "SELECT n.nspname FROM pg_extension e "
                    "JOIN pg_namespace n ON n.oid=e.extnamespace "
                    "WHERE e.extname='vector'"
                )) != "extensions":
                    connection.exec_driver_sql("ALTER EXTENSION vector SET SCHEMA extensions")
                yield connection
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def denied(connection: Connection, statement: str) -> None:
    with connection.begin_nested() as savepoint:
        with pytest.raises(DBAPIError) as failure:
            connection.exec_driver_sql(statement)
        assert getattr(failure.value.orig, "sqlstate", None) == "42501"
        savepoint.rollback()


def test_full_history_and_runtime_grants_do_not_cross_private_boundary(owner: Connection) -> None:
    owner.exec_driver_sql(SQL)
    roles = owner.execute(text(
        "SELECT rolcanlogin, rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls "
        "FROM pg_roles WHERE rolname IN ('jhworks_demo_runtime','jhworks_demo_migrate')"
    )).all()
    assert len(roles) == 2 and all(not any(row) for row in roles)
    owner.exec_driver_sql("SET LOCAL ROLE jhworks_demo_migrate")
    owner.exec_driver_sql("SET LOCAL search_path TO groupware_demo, extensions")
    config = Config(str(ROOT / "apps/api/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "apps/api/alembic"))
    config.attributes["connection"] = owner
    command.upgrade(config, "head")
    assert owner.scalar(text("SELECT version_num FROM alembic_version")) == "f30c9a71b624"
    denied(owner, "SELECT * FROM groupware.private_sentinel")
    owner.exec_driver_sql(
        "CREATE TABLE future_sequence_probe (id bigserial PRIMARY KEY, value text)"
    )
    owner.exec_driver_sql("RESET ROLE")
    # SET ROLE alone keeps the superuser session identity, which could still
    # assume migration. Change session identity to test escalation honestly.
    owner.exec_driver_sql("SET SESSION AUTHORIZATION jhworks_demo_runtime")
    owner.exec_driver_sql("SET LOCAL search_path TO groupware_demo, extensions")
    owner.exec_driver_sql(
        "INSERT INTO departments (id,name,is_active) VALUES ('synthetic','Synthetic demo',true)"
    )
    assert owner.scalar(text("SELECT name FROM departments")) == "Synthetic demo"
    owner.exec_driver_sql("UPDATE departments SET name='Updated synthetic demo'")
    owner.exec_driver_sql("DELETE FROM departments WHERE id='synthetic'")
    assert owner.scalar(text("SELECT count(*) FROM departments")) == 0
    assert owner.scalar(text(
        "INSERT INTO future_sequence_probe (value) VALUES ('synthetic') RETURNING id"
    )) == 1
    denied(owner, "SELECT * FROM groupware.private_sentinel")
    denied(owner, "UPDATE groupware.private_sentinel SET value='changed'")
    denied(owner, "CREATE TABLE forbidden_ddl (id int)")
    denied(owner, "DROP TABLE departments")
    denied(owner, "SET ROLE jhworks_demo_migrate")
    owner.exec_driver_sql("RESET SESSION AUTHORIZATION")
    assert owner.scalar(text("SELECT value FROM groupware.private_sentinel")) == "synthetic-private"
    for role in ("anon", "authenticated"):
        assert not owner.scalar(text(
            "SELECT has_schema_privilege(:role, 'groupware_demo', 'USAGE')"
        ), {"role": role})


def test_rerun_and_public_private_schema_fail_atomically(owner: Connection) -> None:
    owner.exec_driver_sql("GRANT USAGE ON SCHEMA groupware TO PUBLIC")
    with owner.begin_nested() as savepoint:
        with pytest.raises(DBAPIError, match="Private schema is accessible"):
            owner.exec_driver_sql(SQL)
        savepoint.rollback()
    assert owner.scalar(text(
        "SELECT count(*) FROM pg_roles WHERE rolname LIKE 'jhworks_demo_%'"
    )) == 0
    assert not owner.scalar(text("SELECT 1 FROM pg_namespace WHERE nspname='groupware_demo'"))
    owner.exec_driver_sql("REVOKE ALL ON SCHEMA groupware FROM PUBLIC")
    owner.exec_driver_sql(SQL)
    with owner.begin_nested() as savepoint:
        with pytest.raises(DBAPIError, match="already exist"):
            owner.exec_driver_sql(SQL)
        savepoint.rollback()
    assert owner.scalar(text("SELECT value FROM groupware.private_sentinel")) == "synthetic-private"

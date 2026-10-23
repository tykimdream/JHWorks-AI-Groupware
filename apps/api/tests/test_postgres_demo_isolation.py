"""Real migration/grant checks; only disposable loopback PostgreSQL is allowed."""

import hashlib
import os
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast

import pytest
from alembic.config import Config
from psycopg import Connection as PsycopgConnection
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.exc import DBAPIError

from alembic import command

ROOT = Path(__file__).resolve().parents[3]
SQL = (ROOT / "deploy/cloud-run/supabase-demo-bootstrap.sql").read_text(encoding="utf-8")
COMMON_SQL = (ROOT / "deploy/cloud-run/supabase-demo-common.sql").read_text(encoding="utf-8")
RETENTION_SQL = (ROOT / "deploy/cloud-run/verify-demo-retention.sql").read_text(encoding="utf-8")


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
    from app.ops.demo_credentials import database_preflight

    database_preflight(
        cast(PsycopgConnection[Any], owner.connection.driver_connection),
        expected_database="jhworks_test",
    )
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


@pytest.fixture
def common_owner(owner: Connection) -> Connection:
    owner.exec_driver_sql(SQL)
    owner.exec_driver_sql("ALTER ROLE jhworks_demo_runtime LOGIN")
    owner.exec_driver_sql("ALTER ROLE jhworks_demo_migrate LOGIN")
    owner.exec_driver_sql("SET LOCAL ROLE jhworks_demo_migrate")
    owner.exec_driver_sql("SET LOCAL search_path TO groupware_demo, extensions")
    config = Config(str(ROOT / "apps/api/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "apps/api/alembic"))
    config.attributes["connection"] = owner
    command.upgrade(config, "head")
    owner.exec_driver_sql("RESET ROLE")
    owner.exec_driver_sql(
        "INSERT INTO groupware_demo.departments (id,name,is_active) "
        "VALUES ('existing_dept','Existing synthetic team',true)"
    )
    owner.exec_driver_sql(
        "INSERT INTO groupware_demo.work_calendar_events "
        "(id,category,title,start_date,end_date,scope,department_id,status,impact,created_at) "
        "VALUES ('existing_event','COMPANY_EVENT','Existing department event',"
        "CURRENT_DATE,CURRENT_DATE,'DEPARTMENT','existing_dept','CONFIRMED','CAUTION',now())"
    )
    return owner


def test_common_fixtures_preserve_existing_rows_and_refuse_repeat_or_runtime(
    common_owner: Connection,
) -> None:
    db = common_owner
    db.exec_driver_sql(COMMON_SQL)
    policies = db.execute(text(
        "SELECT record_id,title,content_hash FROM groupware_demo.company_policies"
    )).all()
    assert len(policies) == 3
    for record_id, title, content_hash in policies:
        assert title.startswith("[체험·합성]")
        sections = db.execute(text(
            'SELECT section_id,title,content,"order",embedding FROM groupware_demo.policy_sections '
            'WHERE policy_record_id=:record ORDER BY "order"'
        ), {"record": record_id}).all()
        canonical = "\n".join("|".join(row[:3]) for row in sections)
        assert hashlib.sha256(canonical.encode()).hexdigest() == content_hash
        assert [row[3] for row in sections] == list(range(1, len(sections) + 1))
        assert all(row[4] is None for row in sections)
    assert db.scalar(text("SELECT count(*) FROM groupware_demo.policy_sections")) == 10
    from app.scripts.seed import POLICY_RULES

    rules = dict(db.execute(text(
        "SELECT section_id,rule_config FROM groupware_demo.policy_sections "
        "WHERE rule_config IS NOT NULL"
    )).tuples().all())
    assert rules == POLICY_RULES
    headers = db.execute(text(
        "SELECT type,status,version,effective_from FROM groupware_demo.company_policies"
    )).all()
    assert {row[0] for row in headers} == {"TRAVEL", "EXPENSE", "LEAVE"}
    assert all(row[1] == "ACTIVE" and row[2] == "demo-1.0" for row in headers)
    events = db.execute(text(
        "SELECT title,start_date,end_date,department_id,employee_id,approval_id "
        "FROM groupware_demo.work_calendar_events WHERE scope='COMPANY'"
    )).all()
    year = int(db.scalar(text("SELECT extract(year FROM CURRENT_DATE)")))
    assert len(events) == 48
    assert {row[1].year for row in events} == {year, year + 1}
    assert len({(row[1].year, row[1].month) for row in events}) == 24
    assert all(row[0].startswith("[체험·합성]") and row[1] == row[2]
               and row[3:] == (None, None, None) for row in events)
    with db.begin_nested() as savepoint:
        with pytest.raises(DBAPIError, match="Common data already exists"):
            db.exec_driver_sql(COMMON_SQL)
        savepoint.rollback()
    assert db.scalar(text("SELECT count(*) FROM groupware_demo.company_policies")) == 3
    assert db.scalar(text(
        "SELECT title FROM groupware_demo.work_calendar_events WHERE id='existing_event'"
    )) == "Existing department event"
    assert db.scalar(text("SELECT value FROM groupware.private_sentinel")) == "synthetic-private"


@pytest.mark.parametrize("populated", [False, True])
def test_retention_preflight_reports_actual_cleanup_order_without_changes(
    common_owner: Connection, populated: bool,
) -> None:
    from app.ops.staging_backup import BackupProfile, snapshot

    db = common_owner
    now = int(db.scalar(text("SELECT floor(extract(epoch FROM statement_timestamp()))")))
    if populated:
        # a/b tie at the retention boundary; c is expired but not yet eligible.
        # d is still active. The newest empty candidate is not the runner target.
        for letter, offset in [("a", -86400), ("b", -86400), ("c", -60), ("d", 3600)]:
            suffix = letter * 32
            params = {"space": "demo_" + suffix, "dept": "demo_dept_" + suffix,
                      "expiry": now + offset}
            db.execute(text(
                "INSERT INTO groupware_demo.departments (id,name,is_active) "
                "VALUES (:dept,:dept,true)"
            ), params)
            db.execute(text(
                "INSERT INTO groupware_demo.demo_workspaces "
                "(id,department_id,expires_at_epoch,is_active,write_limit,writes_used) "
                "VALUES (:space,:dept,:expiry,true,20,0)"
            ), params)
            for role in ("author", "mgr"):
                employee_id = "demo_" + role + "_" + suffix
                db.execute(text(
                    "INSERT INTO groupware_demo.employees "
                    "(id,name,email,department_id,demo_workspace_id,position,role,"
                    "hire_date,leave_balance,is_active) "
                    "VALUES (:employee,:employee,:email,:dept,:space,'Synthetic','EMPLOYEE',"
                    "CURRENT_DATE,15,true)"
                ), {**params, "employee": employee_id, "email": employee_id + "@jhworks.test"})
        db.execute(text(
            "INSERT INTO groupware_demo.approvals "
            "(id,type,title,content,author_id,status,details,attachment_metadata,version,"
            "created_at,updated_at) VALUES ('retention_probe','GENERAL','Synthetic','Synthetic',"
            ":author,'DRAFT','{}','[]',1,now(),now())"
        ), {"author": "demo_author_" + "a" * 32})
        db.execute(text(
            "INSERT INTO groupware_demo.demo_feedback "
            "(id,workspace_hash,content_hash,category,screen,message,created_at_epoch) "
            "VALUES ('retention_probe',:hash,:hash,'idea','general','Synthetic',:created)"
        ), {"hash": "a" * 64, "created": now - 2592000})

    def query(statement: str) -> Any:
        return db.exec_driver_sql(statement).scalar_one()

    before = snapshot(query, profile=BackupProfile.DEMO)
    db.exec_driver_sql("SET LOCAL ROLE jhworks_demo_runtime")
    report = db.exec_driver_sql(RETENTION_SQL).scalar_one()
    db.exec_driver_sql("RESET ROLE")
    assert snapshot(query, profile=BackupProfile.DEMO) == before
    assert db.scalar(text("SELECT value FROM groupware.private_sentinel")) == "synthetic-private"
    assert report["demo_head"] == "f30c9a71b624"
    assert report["observed_at_epoch"] >= now
    assert report["cleanup_eligible"] == (2 if populated else 0)
    if not populated:
        assert report["next_cleanup"] is None and report["candidate"] is None
        assert report["next_eligible_at_epoch"] is None
    else:
        assert report["workspaces"] == 4 and report["expired_feedback"] == 1
        assert report["next_cleanup"] == {
            "workspace_id": "demo_" + "a" * 32,
            "department_id": "demo_dept_" + "a" * 32,
            "expires_at_epoch": now - 86400,
            "employee_count": 2, "approval_count": 1,
        }
        assert report["candidate"]["workspace_id"] == "demo_" + "c" * 32
        assert report["candidate"]["cleanup_eligible"] is False
        assert report["next_eligible_at_epoch"] == now
    db.exec_driver_sql("SET SESSION AUTHORIZATION jhworks_demo_runtime")
    try:
        assert db.scalar(text("SELECT count(*) FROM groupware_demo.company_policies")) == 3
        with db.begin_nested() as savepoint:
            with pytest.raises(DBAPIError, match="approved operator"):
                db.exec_driver_sql(COMMON_SQL)
            savepoint.rollback()
        denied(db, "SELECT * FROM groupware.private_sentinel")
    finally:
        db.exec_driver_sql("RESET SESSION AUTHORIZATION")


def test_common_fixture_late_failure_rolls_back_inserted_policy_rows(
    common_owner: Connection,
) -> None:
    db = common_owner
    db.exec_driver_sql(
        "ALTER TABLE groupware_demo.work_calendar_events "
        "ADD CONSTRAINT synthetic_reject_common CHECK (scope <> 'COMPANY')"
    )
    with db.begin_nested() as savepoint:
        with pytest.raises(DBAPIError) as error:
            db.exec_driver_sql(COMMON_SQL)
        assert getattr(error.value.orig, "sqlstate", None) == "23514"
        savepoint.rollback()
    assert db.scalar(text("SELECT count(*) FROM groupware_demo.company_policies")) == 0
    assert db.scalar(text("SELECT count(*) FROM groupware_demo.policy_sections")) == 0
    assert db.scalar(text("SELECT count(*) FROM groupware_demo.work_calendar_events")) == 1
    assert db.scalar(text("SELECT value FROM groupware.private_sentinel")) == "synthetic-private"


def test_common_fixture_refuses_private_access_leak(common_owner: Connection) -> None:
    db = common_owner
    db.exec_driver_sql("GRANT USAGE ON SCHEMA groupware TO jhworks_demo_runtime")
    with db.begin_nested() as savepoint:
        with pytest.raises(DBAPIError, match="authenticated isolated demo roles"):
            db.exec_driver_sql(COMMON_SQL)
        savepoint.rollback()
    assert db.scalar(text("SELECT count(*) FROM groupware_demo.company_policies")) == 0


def test_demo_backup_snapshot_captures_only_its_schema(common_owner: Connection) -> None:
    from app.ops.staging_backup import BackupProfile, snapshot

    db = common_owner
    db.exec_driver_sql(COMMON_SQL)
    statements: list[str] = []

    def query(statement: str) -> Any:
        statements.append(statement)
        return db.exec_driver_sql(statement).scalar_one()

    observed = snapshot(query, profile=BackupProfile.DEMO)
    assert observed["head"] == "f30c9a71b624"
    assert len(observed["tables"]) == 16
    assert observed["tables"]["company_policies"]["count"] == 3
    assert observed["tables"]["policy_sections"]["count"] == 10
    assert observed["tables"]["work_calendar_events"]["count"] == 49
    assert "private_sentinel" not in observed["tables"]
    assert all('"groupware".' not in statement and "'groupware'" not in statement
               for statement in statements)
    assert "jhworks_demo_migrate" in str(observed["ownership_acl"])
    assert "jhworks_demo_runtime" in str(observed["schema_acl"])
    assert db.scalar(text("SELECT value FROM groupware.private_sentinel")) == "synthetic-private"

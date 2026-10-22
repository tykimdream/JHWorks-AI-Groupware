"""Rotate only the three pristine private staging fixture credentials, with hidden input."""

import argparse
import getpass
import json
import sys
import warnings
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import psycopg
from sqlalchemy import create_engine, func, literal, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.database import Base
from app.core.security import hash_password, verify_password
from app.models import Credential, Department, Employee, LeaveAccount
from app.models.enums import EmployeeRole
from app.ops.staging_backup import PROJECT, connection_parameters, run
from app.ops.staging_fixture import HEAD, IDS, verify_private_service
from app.ops.staging_workflow import Workflow


def require_pristine_fixture(db: Session, year: int) -> None:
    counts = {"departments": 1, "employees": 3, "credentials": 3, "leave_accounts": 3}
    for table in Base.metadata.sorted_tables:
        expected = counts.get(table.name)
        if expected is None:
            if db.scalar(select(literal(1)).select_from(table).limit(1)) is not None:
                raise ValueError("business data must be reviewed before credential rotation")
        elif db.scalar(select(func.count()).select_from(
            select(literal(1)).select_from(table).limit(expected + 1).subquery(),
        )) != expected:
            raise ValueError("unexpected fixture table count")
    department = db.get(Department, "stg_validation")
    if department is None or department.manager_employee_id != IDS[1] or not department.is_active:
        raise ValueError("unexpected fixture department")
    for employee_id, actor in zip(IDS, ("author", "approver", "unrelated"), strict=True):
        employee = db.get(Employee, employee_id)
        if (employee is None or employee.email != f"staging.{actor}@jhworks.test"
                or employee.department_id != department.id or not employee.is_active
                or employee.role != (EmployeeRole.MANAGER if actor == "approver"
                                     else EmployeeRole.EMPLOYEE)
                or employee.manager_id != (None if actor == "approver" else IDS[1])):
            raise ValueError("unexpected fixture employee")
        if db.get(Credential, employee_id) is None:
            raise ValueError("fixture credential missing")
        account = db.scalar(select(LeaveAccount).where(
            LeaveAccount.employee_id == employee_id, LeaveAccount.year == year,
        ))
        if (account is None or account.granted_days != Decimal("15.0")
                or account.carried_over_days != 0 or account.used_days != 0
                or account.pending_days != 0 or account.version != 1):
            raise ValueError("unexpected fixture leave account")


def rotate_passwords(db: Session, password: str, year: int) -> None:
    if not 20 <= len(password) <= 128 or password != password.strip():
        raise ValueError("use a new private password of 20 to 128 characters")
    require_pristine_fixture(db, year)
    credentials = list(db.scalars(select(Credential).where(Credential.employee_id.in_(IDS))))
    if any(verify_password(password, credential.password_hash) for credential in credentials):
        raise ValueError("the replacement password must differ from every existing password")
    # Compute all hashes before changing rows; the caller owns the atomic transaction.
    replacements = [hash_password(password) for _ in credentials]
    for credential, replacement in zip(credentials, replacements, strict=True):
        credential.password_hash = replacement
    db.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify-workflow", action="store_true")
    args = parser.parse_args()
    stage = "service_verify"
    rotated = False
    workflow: Workflow | None = None
    try:
        verify_private_service(args.commit)
        stage = "database_credentials"
        url = run([
            "gcloud", "secrets", "versions", "access", "1", "--secret",
            "jhworks-migration-database", "--project", PROJECT,
        ], capture_output=True, text=True).stdout.strip()
        parameters = connection_parameters(url, args.ca_file)
        engine = create_engine("postgresql+psycopg://", poolclass=NullPool,
                               creator=lambda: psycopg.connect(**parameters))
        try:
            year = datetime.now(UTC).year
            stage = "database_preflight"
            with Session(engine) as db, db.begin():
                db.execute(text("SET TRANSACTION READ ONLY"))
                db.execute(text("SET LOCAL search_path TO groupware,extensions,public"))
                if db.scalar(text("SELECT version_num FROM groupware.alembic_version")) != HEAD:
                    raise ValueError("unexpected migration head")
                require_pristine_fixture(db, year)
            if not args.apply:
                print(json.dumps({"status": "passed", "mode": "preflight", "changed": 0}))
                return
            stage = "credential_input"
            if not sys.stdin.isatty():
                raise ValueError("credential replacement requires an interactive operator terminal")
            print("Scope: replace passwords for the three private synthetic fixture accounts only.")
            if args.verify_workflow:
                print("Then validate two synthetic approvals and one fixture leave day via HTTP.")
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                password = getpass.getpass("NEW private fixture password (hidden, 20+ chars): ")
                if password != getpass.getpass("Confirm NEW private fixture password (hidden): "):
                    raise ValueError("passwords do not match")
            stage = "service_recheck"
            verify_private_service(args.commit)
            stage = "credential_transaction"
            with Session(engine) as db, db.begin():
                db.execute(text("SET LOCAL search_path TO groupware,extensions,public"))
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                db.execute(text("SET LOCAL statement_timeout = '15s'"))
                names = ",".join(f'groupware."{t.name}"' for t in Base.metadata.sorted_tables)
                db.execute(text(f"LOCK TABLE {names} IN SHARE ROW EXCLUSIVE MODE"))
                if db.scalar(text("SELECT version_num FROM groupware.alembic_version")) != HEAD:
                    raise ValueError("migration changed after preflight")
                rotate_passwords(db, password, year)
            print(json.dumps({"status": "passed", "rotatedCredentials": 3}))
            rotated = True
            if args.verify_workflow:
                workflow = Workflow({})
                workflow.run_remote(password, args.commit)
                print(json.dumps({"status": "passed", "mode": "workflow",
                                  "checks": workflow.passed,
                                  "createdApprovals": 2, "usedLeaveDays": 1}))
        finally:
            engine.dispose()
    except Exception as error:
        # Password/hash/DB/HTTP exception details must never be printed.
        print(json.dumps({"status": "failed", "stage": workflow.stage if workflow else stage,
                          "errorType": type(error).__name__,
                          "rotatedCredentials": 3 if rotated else 0}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

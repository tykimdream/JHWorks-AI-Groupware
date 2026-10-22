"""Operator-run, one-time fixture for the empty, IAM-private staging database."""

import argparse
import getpass
import hashlib
import json
import re
import sys
import warnings
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from sqlalchemy import create_engine, literal, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.database import Base
from app.core.security import hash_password
from app.models import Credential, Department, Employee, LeaveAccount
from app.models.enums import EmployeeRole
from app.ops.staging_backup import PROJECT, connection_parameters, run

HEAD = "c84f2a19d6e0"
SERVICE = "jhworks-staging"
REGION = "asia-northeast3"
IDS = ("stg_author_001", "stg_approver_001", "stg_unrelated_001")


def verify_backup(reference: str, root: Path) -> None:
    match = re.fullmatch(
        r"cloud-shell:(\d{8}T\d{6}Z-[a-f0-9]{8}):sha256:([a-f0-9]{64}):restore-verified",
        reference,
    )
    if match is None:
        raise ValueError("an actual restore-verified backup reference is required")
    directory = root / match[1]
    report = json.loads((directory / "verification.json").read_text(encoding="utf-8"))
    if (
        report.get("status") != "passed"
        or report.get("temporaryContainerRemoved") is not True
        or report.get("head") != HEAD
        or report.get("backupReference") != reference
        or report.get("dumpSha256") != match[2]
        or hashlib.sha256((directory / "groupware.dump").read_bytes()).hexdigest() != match[2]
    ):
        raise ValueError("backup archive or verification does not match")


def verify_private_service(commit: str) -> None:
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("a full deployed commit SHA is required")

    def read(arguments: list[str]) -> dict[str, Any]:
        value = json.loads(run(
            ["gcloud", *arguments, "--project", PROJECT, "--format=json"],
            capture_output=True, text=True,
        ).stdout)
        if not isinstance(value, dict):
            raise ValueError("invalid GCP response")
        return value

    service = read(["run", "services", "describe", SERVICE, "--region", REGION])
    if read(["projects", "describe", PROJECT]).get("projectNumber") != "968398406137":
        raise ValueError("unexpected GCP project")
    policies = [
        read(["run", "services", "get-iam-policy", SERVICE, "--region", REGION]),
        read(["projects", "get-iam-policy", PROJECT]),
    ]
    annotations = service["metadata"].get("annotations", {})
    expected = f"{SERVICE}-{commit[:12]}"
    traffic = service["status"].get("traffic", [])
    if (
        service["status"].get("latestReadyRevisionName") != expected
        or sum(item.get("percent", 0) for item in traffic
               if item.get("revisionName") == expected) != 100
        or annotations.get("run.googleapis.com/invoker-iam-disabled") == "true"
        or annotations.get("run.googleapis.com/maxScale") != "2"
        or any(member in {"allUsers", "allAuthenticatedUsers"}
               for policy in policies for binding in policy.get("bindings", [])
               for member in binding.get("members", []))
    ):
        raise ValueError("expected private staging revision and IAM boundary")
    api = next(c for c in service["spec"]["template"]["spec"]["containers"] if c["name"] == "api")
    if not any(e.get("name") == "JHWORKS_AI_ENABLED" and e.get("value") == "false"
               for e in api["env"]):
        raise ValueError("AI must remain disabled")


def require_empty(db: Session) -> None:
    for table in Base.metadata.sorted_tables:
        if db.scalar(select(literal(1)).select_from(table).limit(1)) is not None:
            raise ValueError("fixture requires all business tables to be empty")


def populate(db: Session, password: str, year: int) -> None:
    if not 20 <= len(password) <= 128 or password != password.strip():
        raise ValueError("use a private password of 20 to 128 characters without outer spaces")
    if not 2000 <= year <= 2100:
        raise ValueError("unsupported fixture year")
    require_empty(db)
    department = Department(id="stg_validation", name="Synthetic staging validation")
    db.add(department)
    db.flush()
    approver = Employee(
        id=IDS[1], name="합성 검증 결재자", email="staging.approver@jhworks.test",
        department_id=department.id, position="검증 결재자", role=EmployeeRole.MANAGER,
        hire_date=date(year, 1, 1), leave_balance=Decimal("15.0"),
    )
    db.add(approver)
    db.flush()
    for employee_id, name, email in [
        (IDS[0], "합성 검증 작성자", "staging.author@jhworks.test"),
        (IDS[2], "합성 검증 비참여자", "staging.unrelated@jhworks.test"),
    ]:
        db.add(Employee(
            id=employee_id, name=name, email=email, department_id=department.id,
            position="검증 직원", role=EmployeeRole.EMPLOYEE, manager_id=approver.id,
            hire_date=date(year, 1, 1), leave_balance=Decimal("15.0"),
        ))
    department.manager_employee_id = approver.id
    db.flush()
    for employee_id in IDS:
        db.add(Credential(employee_id=employee_id, password_hash=hash_password(password)))
        db.add(LeaveAccount(
            id=f"stg_leave_{employee_id}_{year}", employee_id=employee_id, year=year,
            granted_days=Decimal("15.0"),
        ))
    db.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--backup-reference", required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    stage = "backup_verify"
    try:
        verify_backup(args.backup_reference, Path.home() / "jhworks-staging-backups")
        stage = "service_verify"
        verify_private_service(args.commit)
        stage = "database_credentials"
        url = run([
            "gcloud", "secrets", "versions", "access", "1", "--secret",
            "jhworks-migration-database", "--project", PROJECT,
        ], capture_output=True, text=True).stdout.strip()
        parameters = connection_parameters(url, args.ca_file)
        engine = create_engine(
            "postgresql+psycopg://", poolclass=NullPool,
            creator=lambda: psycopg.connect(**parameters),
        )
        try:
            stage = "database_preflight"
            with Session(engine) as db, db.begin():
                db.execute(text("SET TRANSACTION READ ONLY"))
                db.execute(text("SET LOCAL search_path TO groupware,extensions,public"))
                if db.scalar(text("SELECT version_num FROM groupware.alembic_version")) != HEAD:
                    raise ValueError("unexpected migration head")
                require_empty(db)
            print("Private staging and empty business database checks passed.")
            if not args.apply:
                print("Preflight only; no accounts created.")
                return
            stage = "operator_confirmation"
            if not sys.stdin.isatty():
                raise ValueError("credential setup requires the operator's interactive terminal")
            if input("Type CREATE PRIVATE FIXTURE to continue: ") != "CREATE PRIVATE FIXTURE":
                raise ValueError("operator confirmation missing")
            stage = "credential_input"
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                password = getpass.getpass("Private fixture password (hidden, 20+ characters): ")
                if password != getpass.getpass("Confirm private fixture password (hidden): "):
                    raise ValueError("passwords do not match")
            stage = "service_recheck"
            verify_private_service(args.commit)
            stage = "fixture_transaction"
            with Session(engine) as db, db.begin():
                db.execute(text("SET LOCAL search_path TO groupware,extensions,public"))
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                db.execute(text("SET LOCAL statement_timeout = '15s'"))
                # Serialize fixture initialization against any concurrent writer.
                names = ",".join(f'groupware."{t.name}"' for t in Base.metadata.sorted_tables)
                db.execute(text(f"LOCK TABLE {names} IN SHARE ROW EXCLUSIVE MODE"))
                if db.scalar(text("SELECT version_num FROM groupware.alembic_version")) != HEAD:
                    raise ValueError("migration changed after preflight")
                populate(db, password, datetime.now(UTC).year)
            print(json.dumps({"status": "passed", "departments": 1, "employees": 3,
                              "credentials": 3, "leaveAccounts": 3}))
        finally:
            engine.dispose()
    except Exception as error:
        # DB exceptions can contain bound password hashes; never print them.
        print(json.dumps({"status": "failed", "stage": stage, "errorType": type(error).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

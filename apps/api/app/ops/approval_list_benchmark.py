"""Synthetic ORM/serialization baseline in a dedicated loopback PostgreSQL schema."""

import argparse
import json
import os
import platform
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

FIXTURE_VERSION = "approval-list-v1"


def dedicated_url(raw: str) -> URL:
    url = make_url(raw)
    if (url.drivername != "postgresql+psycopg"
            or url.host not in {"127.0.0.1", "localhost", "::1"}
            or url.database != "jhworks_test" or url.username != "jhworks_test"
            or url.query):
        raise ValueError("requires loopback jhworks_test database/user without URL options")
    return url


def bounded_counts(raw: str) -> list[int]:
    counts = [int(value) for value in raw.split(",")]
    if not counts or len(counts) > 3 or len(set(counts)) != len(counts):
        raise ValueError("provide 1 to 3 distinct document counts")
    if any(value < 4 or value > 10000 for value in counts):
        raise ValueError("each document count must be between 4 and 10000")
    return counts


def seed(db: Session, count: int) -> dict[str, str]:
    from app.models import Approval, ApprovalLine, Department, Employee
    from app.models.enums import ApprovalLineStatus, ApprovalStatus, ApprovalType, EmployeeRole

    db.add(Department(id="bench-dept", name="Synthetic benchmark department"))
    db.flush()
    actors = {name: f"bench-{name}" for name in ("author", "approver", "other", "outsider")}
    for name, actor_id in actors.items():
        db.add(Employee(id=actor_id, name=f"Synthetic {name}", email=f"{name}@benchmark.test",
                        department_id="bench-dept", position="Synthetic fixture",
                        role=EmployeeRole.EMPLOYEE, hire_date=date(2026, 1, 1)))
    db.flush()
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    for index in range(count):
        document_id = f"bench-document-{index:05d}"
        db.add(Approval(
            id=document_id, type=ApprovalType.EXPENSE, title=f"Synthetic expense {index:05d}",
            content="Synthetic expense body. " * 40,
            author_id=actors["other"] if index % 4 == 0 else actors["author"],
            status=ApprovalStatus.PENDING, amount=170000,
            details={"kind": "EXPENSE", "expenseDate": "2026-01-01", "merchant": "Synthetic",
                     "category": "OTHER", "purpose": "Synthetic benchmark"},
            attachment_metadata=[{"name": "synthetic.pdf", "contentType": "application/pdf"}],
            version=4, created_at=clock, updated_at=clock + timedelta(seconds=index // 4),
            submitted_at=clock,
        ))
    db.flush()
    for index in range(count):
        for round_number in (1, 2):
            db.add(ApprovalLine(
                id=f"bench-line-{index:05d}-{round_number}",
                approval_id=f"bench-document-{index:05d}", step=1, round=round_number,
                approver_id=actors["approver"],
                status=ApprovalLineStatus.REJECTED if round_number == 1
                else ApprovalLineStatus.PENDING,
                comment="Synthetic revision requested" if round_number == 1 else None,
            ))
    db.commit()
    return actors


def measure(factory: sessionmaker[Session], actor_id: str, scope: str) -> dict[str, Any]:
    from app.models import Employee
    from app.schemas.approval import ApprovalListResponse
    from app.services.approval import list_approvals
    from app.services.mappers import approval_read

    with factory() as db:
        actor = db.get(Employee, actor_id)
        assert actor is not None
        statements = 0
        connection = db.connection()

        def count_query(*args: Any, **kwargs: Any) -> None:
            nonlocal statements
            statements += 1

        event.listen(connection, "before_cursor_execute", count_query)
        try:
            started = perf_counter()
            items = list_approvals(db, actor, scope)
            loaded = perf_counter()
            response = ApprovalListResponse(items=[approval_read(item) for item in items],
                                            total=len(items))
            payload = response.model_dump_json(by_alias=True).encode("utf-8")
            finished = perf_counter()
            return {"rows": len(items), "sqlStatements": statements,
                    "payloadBytes": len(payload), "ormMs": (loaded - started) * 1000,
                    "mapSerializeMs": (finished - loaded) * 1000,
                    "totalMs": (finished - started) * 1000}
        finally:
            event.remove(connection, "before_cursor_execute", count_query)


def run(raw: str, counts: list[int], repeats: int) -> dict[str, Any]:
    url = dedicated_url(raw)
    # Validate before importing any application settings or connecting to a DB.
    if not 1 <= repeats <= 5 or bounded_counts(",".join(map(str, counts))) != counts:
        raise ValueError("repeats must be between 1 and 5")
    from app.models import Approval

    engine = create_engine(url)
    results: list[dict[str, Any]] = []
    try:
        with engine.connect() as connection:
            postgres_version = str(connection.scalar(text("SHOW server_version")))
        for count in counts:
            schema = "approval_bench_" + uuid4().hex
            scoped = engine.execution_options(schema_translate_map={None: schema})
            created = False
            try:
                with scoped.begin() as connection:
                    # Vector must be provisioned on the disposable test DB, never by this tool.
                    connection.execute(CreateSchema(schema))
                    created = True
                    Approval.metadata.create_all(connection)
                factory = sessionmaker(bind=scoped, expire_on_commit=False)
                with factory() as db:
                    actors = seed(db, count)
                with scoped.begin() as connection:
                    # Statistics matter for comparisons; only this tool's random schema is analyzed.
                    for table in Approval.metadata.sorted_tables:
                        connection.execute(text(f'ANALYZE "{schema}"."{table.name}"'))
                for actor, scope in (("author", "mine"), ("approver", "assigned"),
                                     ("outsider", "assigned")):
                    measure(factory, actors[actor], scope)  # One unreported warm-up per case.
                    samples = [measure(factory, actors[actor], scope) for _ in range(repeats)]
                    results.append({"documents": count, "actor": actor, "scope": scope,
                                    "samples": samples,
                                    "medianTotalMs": median(s["totalMs"] for s in samples)})
            finally:
                if created:
                    with scoped.begin() as connection:
                        connection.execute(DropSchema(schema, cascade=True))
    finally:
        engine.dispose()
    return {"fixtureVersion": FIXTURE_VERSION, "sourceSha": os.getenv("GITHUB_SHA", "local"),
            "pythonVersion": platform.python_version(), "postgresVersion": postgres_version,
            "repeats": repeats, "warmupPerCase": 1, "concurrency": 1,
            "boundary": "ORM + mapper + JSON; excludes actor lookup, HTTP/auth, network, UI",
            "cache": "fresh ORM session per sample; shared PostgreSQL buffers, not cold cache",
            "cases": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", default="100,1000")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run(os.environ.get("JHWORKS_TEST_POSTGRES_URL", ""),
                     bounded_counts(args.counts), args.repeats)
    except (ValueError, TypeError):
        parser.error("invalid dedicated test database configuration or bounded run parameters")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Synthetic baseline: {len(report['cases'])} cases; report saved (no database URL).")


if __name__ == "__main__":
    main()

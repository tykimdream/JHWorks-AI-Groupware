"""Bounded demo retention runner. Dry-run by default; no public HTTP endpoint."""

import argparse
import json
from collections.abc import Callable
from typing import Any

from sqlalchemy import Connection, event
from sqlalchemy.orm import Session, SessionTransaction

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.demo_cleanup import cleanup_expired_demo
from app.services.demo_feedback import purge_expired_feedback


def transaction_timeouts(
    _session: Session, _transaction: SessionTransaction, connection: Connection
) -> None:
    if connection.dialect.name == "postgresql":
        connection.exec_driver_sql("SET LOCAL statement_timeout = '15s'")
        connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")


def run_maintenance(
    factory: Callable[[], Session], *, apply: bool = False, batch_size: int = 5
) -> dict[str, Any]:
    if not 1 <= batch_size <= 10:
        raise ValueError("Maintenance batch must be 1..10")
    report: dict[str, Any] = {
        "status": "running",
        "dryRun": not apply,
        "stage": "feedback",
        "steps": {},
    }
    try:
        # Feedback has an independent retention promise. A malformed workspace must
        # not prevent its purge. Each stage commits separately; retries are safe.
        with factory() as db:
            event.listen(db, "after_begin", transaction_timeouts)
            feedback = purge_expired_feedback(db, apply=apply)
        report["steps"]["feedback"] = {
            "expired": feedback.expired,
            "removed": feedback.removed,
            "stored": feedback.stored,
        }
        report["stage"] = "workspaces"
        with factory() as db:
            event.listen(db, "after_begin", transaction_timeouts)
            workspaces = cleanup_expired_demo(db, apply=apply, batch_size=batch_size)
        report["steps"]["workspaces"] = {
            "planned": workspaces.planned,
            "removed": workspaces.removed,
        }
        report.update(status="passed", stage="complete", severity="INFO")
    except Exception as exc:
        # Exception messages can contain connection strings or stored feedback.
        report.update(status="failed", severity="ERROR", errorType=type(exc).__name__)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--batch-size", type=int, default=5, choices=range(1, 11))
    args = parser.parse_args()
    settings = get_settings()
    if not settings.public_demo_enabled or settings.ai_enabled:
        parser.error("Maintenance requires explicit public demo configuration and AI disabled")
    report = run_maintenance(SessionLocal, apply=args.apply, batch_size=args.batch_size)
    print(json.dumps(report))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()

"""Private operator access. Text export and actual retention deletion are explicit options."""

import argparse
import json

from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.demo_feedback import DemoFeedback
from app.services.demo_feedback import RETENTION_SECONDS
from app.services.login_budget import database_seconds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-text", action="store_true")
    parser.add_argument("--purge-expired", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if not get_settings().public_demo_enabled or not 1 <= args.limit <= 50:
        parser.error("Explicit public demo configuration and limit 1..50 are required")
    if args.apply and not args.purge_expired:
        parser.error("--apply requires --purge-expired")
    try:
        with SessionLocal() as db:
            cutoff = database_seconds(db) - RETENTION_SECONDS
            expired = (
                db.scalar(
                    select(func.count())
                    .select_from(DemoFeedback)
                    .where(
                        DemoFeedback.created_at_epoch <= cutoff,
                    )
                )
                or 0
            )
            report: dict[str, object] = {
                "status": "passed",
                "expired": expired,
                "retentionDays": 30,
                "removed": 0,
            }
            if args.purge_expired and args.apply:
                db.execute(delete(DemoFeedback).where(DemoFeedback.created_at_epoch <= cutoff))
                db.commit()
                report["removed"] = expired
            report["stored"] = db.scalar(select(func.count()).select_from(DemoFeedback)) or 0
            if args.include_text:
                report["submissions"] = [
                    {
                        "id": row.id,
                        "category": row.category,
                        "screen": row.screen,
                        "message": row.message,
                        "createdAtEpoch": row.created_at_epoch,
                    }
                    for row in db.scalars(
                        select(DemoFeedback)
                        .where(
                            DemoFeedback.created_at_epoch > cutoff,
                        )
                        .order_by(DemoFeedback.created_at_epoch.desc(), DemoFeedback.id)
                        .limit(args.limit)
                    )
                ]
            print(json.dumps(report, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"status": "failed", "errorType": type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

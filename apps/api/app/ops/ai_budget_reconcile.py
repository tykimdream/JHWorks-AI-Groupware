"""Inspect up to five interrupted AI reservations; never refund unknown billing."""

import argparse
import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.ai_budget import AIBudgetReservation
from app.services import ai_budget
from app.services.login_budget import database_seconds


def reconcile(
    factory: sessionmaker[Session],
    reservation_ids: Sequence[str],
    *,
    apply: bool = False,
    public_ai_enabled: bool = False,
    confirmed_no_live_calls: bool = False,
) -> list[dict[str, str | int | bool | None]]:
    ids = list(reservation_ids)
    if len(ids) > 5 or len(set(ids)) != len(ids):
        raise ValueError("Use at most five unique reservation IDs")
    if apply and (not ids or public_ai_enabled or not confirmed_no_live_calls):
        raise ValueError("Apply requires explicit IDs, public AI OFF and confirmed no live calls")
    with factory() as db:
        statement = (
            select(AIBudgetReservation)
            .order_by(AIBudgetReservation.created_at_epoch, AIBudgetReservation.id)
            .limit(5)
        )
        statement = (
            statement.where(AIBudgetReservation.id.in_(ids))
            if ids
            else statement.where(AIBudgetReservation.status == "RESERVED")
        )
        rows = list(db.scalars(statement))
        if ids and set(ids) != {row.id for row in rows}:
            raise ValueError("Unknown reservation ID; no settlement performed")
        now = database_seconds(db)
        report: list[dict[str, str | int | bool | None]] = [
            {
                "id": row.id,
                "status": row.status,
                "maximumMicroUsd": row.maximum_micro_usd,
                "chargedMicroUsd": row.charged_micro_usd,
                "eligible": now - row.created_at_epoch >= 600
                and row.status in {"RESERVED", "UNCERTAIN"},
                "applied": False,
            }
            for row in rows
        ]
    if apply:
        if not all(row["eligible"] for row in report):
            raise ValueError("Every target must be RESERVED/UNCERTAIN and at least ten minutes old")
        for row in report:
            with factory() as db:
                receipt = ai_budget.settle(db, str(row["id"]), actual_micro_usd=None)
            row.update(
                status=receipt.status, chargedMicroUsd=receipt.charged_micro_usd, applied=True
            )
    return report


def main() -> None:
    from app.core.config import get_settings
    from app.core.database import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reservation-id", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-no-live-provider-calls", action="store_true")
    args = parser.parse_args()
    report = reconcile(
        SessionLocal,
        args.reservation_id,
        apply=args.apply,
        public_ai_enabled=get_settings().public_expense_ai_enabled,
        confirmed_no_live_calls=args.confirm_no_live_provider_calls,
    )
    print(json.dumps({"mode": "apply" if args.apply else "dry-run", "reservations": report}))


if __name__ == "__main__":
    main()

"""Dry-run by default; actual external deletion needs a reviewed operational approval."""

import argparse
import json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.demo_cleanup import cleanup_expired_demo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--batch-size", type=int, default=5)
    args = parser.parse_args()
    if not get_settings().public_demo_enabled:
        parser.error("Cleanup is only available in explicitly configured public demo mode")
    try:
        with SessionLocal() as db:
            result = cleanup_expired_demo(db, apply=args.apply, batch_size=args.batch_size)
        print(
            json.dumps(
                {
                    "status": "passed",
                    "dryRun": not args.apply,
                    "planned": result.planned,
                    "removed": result.removed,
                }
            )
        )
    except Exception as exc:
        print(json.dumps({"status": "failed", "errorType": type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

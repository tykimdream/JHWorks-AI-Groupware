"""Offline contract validation for additional synthetic expense challenge cases."""

import json
from pathlib import Path

from app.evals.draft_contract import catalog_report

CHALLENGE_PATH = Path(__file__).parents[2] / "evals" / "expense_challenge_cases.json"


def main() -> int:
    print(json.dumps(catalog_report(CHALLENGE_PATH), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

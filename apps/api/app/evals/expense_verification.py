"""Evaluate deterministic expense correspondence with injected candidate errors, offline only."""

import json
from datetime import date

from app.ai.approval_draft import ApprovalDraftCandidate, ApprovalDraftProviderInput, DraftIntent
from app.core.enums import ExpenseCategory
from app.services.expense_grounding import check_expense_input


def evaluate() -> dict[str, object]:
    value = ApprovalDraftProviderInput(
        request=(
            "금액: 17만원; 지출일: 2026-08-24; 사용처: 코레일; 분류: 교통비; "
            "목적: CES 출장; 증빙 참조: RCP-001"
        ),
        answers=[],
        current_date=date(2026, 8, 25),
        timezone="Asia/Seoul",
    )
    gold = ApprovalDraftCandidate(
        intent=DraftIntent.EXPENSE,
        amount=170000,
        expense_date=date(2026, 8, 24),
        merchant="코레일",
        expense_category=ExpenseCategory.TRANSPORTATION,
        expense_purpose="CES 출장",
        receipt_reference="RCP-001",
    )
    rows: list[dict[str, object]] = []
    _, baseline = check_expense_input(gold, value)
    rows.append({"id": "supported-baseline", "passed": baseline.status == "INPUT_MATCHED"})
    mutations: dict[str, object] = {
        "amount": 180000,
        "expense_date": date(2026, 8, 23),
        "merchant": "미제공 사용처",
        "expense_category": ExpenseCategory.MEALS,
        "expense_purpose": "미제공 업무 목적",
        "receipt_reference": "INVENTED-REF",
    }
    for field, wrong in mutations.items():
        candidate = ApprovalDraftCandidate.model_validate({**gold.model_dump(), field: wrong})
        cleaned, report = check_expense_input(candidate, value)
        passed = report.status == "NEEDS_INPUT" and getattr(cleaned, field) is None
        rows.append({"id": f"injected-{field}", "passed": passed})
    stale, report = check_expense_input(
        gold,
        value.model_copy(update={"answers": ["금액: 18만원"]}),
    )
    rows.append({"id": "stale-amount-after-correction", "passed": stale.amount is None})
    return {
        "kind": "offline-injected-candidate-regression",
        "version": "expense-verification-v1",
        "modelCalls": 0,
        "cases": rows,
        "passed": all(r["passed"] for r in rows),
        "limitations": "Not actual model accuracy, independent holdout, or receipt authenticity.",
    }


if __name__ == "__main__":
    result = evaluate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)

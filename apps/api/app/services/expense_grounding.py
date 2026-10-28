"""Conservative input correspondence, not a semantic truth or receipt authenticity judge.

Expense facts must match explicit labels or supported literal input spans.
Unsupported language fails closed into follow-up questions; no model judge or paid retry.
"""

import re
from datetime import date, timedelta
from decimal import Decimal
from typing import NamedTuple

from app.ai.approval_draft import ApprovalDraftCandidate, ApprovalDraftProviderInput, DraftIntent
from app.core.enums import ExpenseCategory
from app.schemas.expense_grounding import ExpenseFieldCheck, ExpenseGroundingRead

FIELDS = {
    "amount": ("금액", "총액", "지출 금액"),
    "expense_date": ("지출일", "결제일", "사용일"),
    "merchant": ("사용처", "상호"),
    "expense_category": ("분류", "비용 구분"),
    "expense_purpose": ("목적", "업무 목적"),
    "receipt_reference": ("증빙 참조", "영수증 참조"),
}
CATEGORIES = {
    "교통비": ExpenseCategory.TRANSPORTATION,
    "숙박비": ExpenseCategory.LODGING,
    "식비": ExpenseCategory.MEALS,
    "기타": ExpenseCategory.OTHER,
}


class Source(NamedTuple):
    source_index: int
    start: int
    end: int
    text: str


def _labelled(sources: list[str], labels: tuple[str, ...]) -> list[Source]:
    all_labels = "|".join(re.escape(label) for group in FIELDS.values() for label in group)
    pattern = re.compile(
        r"(?:^|[;；\n]|,\s*(?=(?:"
        + all_labels
        + r")\s*[:：=]))\s*(?:"
        + "|".join(re.escape(label) for label in labels)
        + r")\s*[:：=]\s*(.*?)(?=\s*(?:[;；\n]|,\s*(?:"
        + all_labels
        + r")\s*[:：=])|$)"
    )
    for index in range(len(sources) - 1, -1, -1):
        found = [
            Source(index, m.start(1), m.start(1) + len(m[1].rstrip()), m[1].strip())
            for m in pattern.finditer(sources[index])
        ]
        if found:
            return found  # Latest explicitly labelled turn supersedes earlier facts.
    return []


def _krw(text: str) -> int | None:
    match = re.fullmatch(r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(만)?\s*원", text)
    if not match or len(match[1].replace(",", "").replace(".", "")) > 12:
        return None
    value = Decimal(match[1].replace(",", "")) * (10000 if match[2] else 1)
    return int(value) if value == int(value) else None


def check_expense_input(
    candidate: ApprovalDraftCandidate,
    value: ApprovalDraftProviderInput,
) -> tuple[ApprovalDraftCandidate, ExpenseGroundingRead]:
    if candidate.intent != DraftIntent.EXPENSE:
        return candidate, ExpenseGroundingRead(status="NOT_APPLICABLE", checks=[])
    sources = [value.request, *value.answers]
    checks: list[ExpenseFieldCheck] = []
    clear: dict[str, None] = {}
    for field, labels in FIELDS.items():
        actual = getattr(candidate, field)
        if actual is None:
            checks.append(ExpenseFieldCheck(field=field, status="MISSING"))
            continue
        evidence = _labelled(sources, labels)
        if field == "amount" and not evidence:
            evidence = [
                Source(index, m.start(), m.end(), m[0])
                for index, text in enumerate(sources)
                for m in re.finditer(r"(?<![\d.,+-])\d+(?:,\d{3})*(?:\.\d+)?\s*(?:만)?\s*원", text)
            ]
        if not evidence and field in {"merchant", "expense_purpose", "receipt_reference"}:
            # Verbatim correspondence only; this is deliberately not semantic entailment.
            evidence = [
                Source(index, m.start(), m.end(), m[0])
                for index, text in enumerate(sources)
                for m in re.finditer(re.escape(actual), text)
            ]
        if not evidence and field == "expense_category":
            evidence = [
                Source(index, m.start(), m.end(), m[0])
                for index, text in enumerate(sources)
                for m in re.finditer("|".join(CATEGORIES), text)
            ]
        if not evidence and field == "expense_date":
            evidence = [
                Source(index, m.start(), m.end(), m[0])
                for index, text in enumerate(sources)
                if not re.search(r"출장\s*(기간|일|시작|종료)|일정", text)
                for m in re.finditer(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", text)
            ]
        # Corrections without explicit field boundaries cannot safely disambiguate stale facts.
        labelled = _labelled(sources, labels)
        latest_label = labelled[0].source_index if labelled else -1
        if any(
            index > latest_label and re.search(r"아니|취소|정정|말고|수정", text)
            for index, text in enumerate(sources)
        ):
            evidence = []
        supported: list[Source] = []
        for item in evidence:
            if field == "amount":
                matches = _krw(item.text) == actual
            elif field == "expense_date":
                assert isinstance(actual, date)
                relative = {
                    "오늘": value.current_date,
                    "어제": value.current_date - timedelta(days=1),
                }
                matches = item.text == actual.isoformat() or relative.get(item.text) == actual
            elif field == "expense_category":
                matches = CATEGORIES.get(item.text) == actual or item.text == actual.value
            else:
                matches = item.text == actual
            if matches:
                supported.append(item)
        # Multiple distinct values are ambiguous, even if one happens to match the model.
        distinct = {_krw(x.text) if field == "amount" else x.text for x in evidence}
        if supported and len(distinct) == 1:
            item = supported[-1]
            checks.append(
                ExpenseFieldCheck(
                    field=field,
                    status="INPUT_MATCHED",
                    source_index=item.source_index,
                    start=item.start,
                    end=item.end,
                )
            )
        else:
            clear[field] = None
            checks.append(ExpenseFieldCheck(field=field, status="UNVERIFIED"))
    cleaned = candidate.model_copy(update=clear)
    # Do not let unverified free-form model prose reintroduce invented facts or policy advice.
    purpose = cleaned.expense_purpose or "경비"
    paid = cleaned.expense_date.isoformat() if cleaned.expense_date else "미확인"
    cleaned = cleaned.model_copy(
        update={
            "title": f"{purpose[:100]} 경비 정산",
            "content": "\n".join(
                [
                    f"업무 목적: {cleaned.expense_purpose or '미확인'}",
                    f"지출일: {paid}",
                    f"사용처: {cleaned.merchant or '미확인'}",
                    f"금액: {cleaned.amount if cleaned.amount is not None else '미확인'}원",
                ]
            ),
        }
    )
    # Receipt reference is optional for a draft, but an unverified supplied value must be resolved.
    needs_input = any(c.status == "UNVERIFIED" for c in checks) or any(
        c.status == "MISSING" and c.field != "receipt_reference" for c in checks
    )
    return cleaned, ExpenseGroundingRead(
        status="NEEDS_INPUT" if needs_input else "INPUT_MATCHED",
        checks=checks,
    )

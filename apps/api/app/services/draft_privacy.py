"""Fail-closed provider boundary for draft user text.

Every non-whitespace input span is replaced, rather than relying on named-entity detection.
Only fixed, server-owned topic hints may be sent alongside opaque tokens.
"""

import re
from dataclasses import dataclass

from app.ai.approval_draft import ApprovalDraftProviderInput
from app.core.errors import DomainValidationError
from app.services.expense_grounding import CATEGORIES, FIELDS, _labelled

TOPICS = {
    "인터뷰": "인터뷰 결과 보고",
    "면담": "인터뷰 결과 보고",
    "회의": "회의 결과 보고",
    "구매": "구매 요청",
    "구독": "소프트웨어 구독 구매 요청",
    "라이선스": "소프트웨어 구독 구매 요청",
    "자료": "업무 자료 제공 협조 요청",
    "시작": "프로젝트 착수",
    "착수": "프로젝트 착수",
    "예산": "예산 요청",
    "장애": "장애 보고",
    "협조": "업무 협조 요청",
    "계약": "계약 검토",
    "권한": "권한 요청",
    "프로젝트": "프로젝트 보고",
    "출장": "출장 신청",
    "경비": "경비 정산",
    "정산": "경비 정산",
    "휴가": "휴가 신청",
    "교육": "교육 신청",
    "행사": "행사 요청",
}
FIELD_NAMES = {
    "amount": "amount",
    "expense_date": "expense_date",
    "merchant": "merchant",
    "expense_category": "expense_category",
    "expense_purpose": "expense_purpose",
    "receipt_reference": "receipt_reference",
}
TOKEN = re.compile(r"⟦P\d{4}⟧")


@dataclass
class MaskedDraftInput:
    value: ApprovalDraftProviderInput
    topic_query: str


def mask_draft_input(value: ApprovalDraftProviderInput) -> MaskedDraftInput:
    originals: dict[str, str] = {}
    identifiers: dict[str, str] = {}

    def mask(text: str) -> str:
        def replace(match: re.Match[str]) -> str:
            original = match.group()
            if original not in identifiers:
                if len(identifiers) >= 9999:
                    raise DomainValidationError("DRAFT_INPUT_TOO_COMPLEX", "Input is too complex")
                token = f"⟦P{len(identifiers) + 1:04d}⟧"
                identifiers[original] = token
                originals[token] = original
            return identifiers[original]

        return re.sub(r"\S+", replace, text)

    all_text = "\n".join([value.request, *value.answers])
    hints = list(dict.fromkeys(label for keyword, label in TOPICS.items() if keyword in all_text))
    masked = ApprovalDraftProviderInput(
        request=mask(value.request),
        answers=[mask(answer) for answer in value.answers],
        current_date=value.current_date,
        timezone=value.timezone,
        revision_context=mask(value.revision_context) if value.revision_context else None,
        topic_hints=hints,
        private_token_map=originals,
    )
    for field, labels in FIELDS.items():
        matches = _labelled([value.request, *value.answers], labels)
        if len(matches) == 1:
            masked.field_hints[FIELD_NAMES[field]] = mask(matches[0].text)
            if field == "expense_category":
                masked.expense_category_hint = CATEGORIES.get(matches[0].text)
    masked.private_token_map = originals
    return MaskedDraftInput(value=masked, topic_query=" ".join(hints))


def restore_text(text: str, originals: dict[str, str]) -> str:
    return TOKEN.sub(lambda match: originals.get(match.group(), match.group()), text)

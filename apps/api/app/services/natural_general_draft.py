"""Source-preserving formatting for unlabelled general approval requests.

This is not semantic fact checking. It retains every nonempty source span in order,
uses a small fixed set of headings and supports only a reversible ending change.
"""

import re
from dataclasses import dataclass

from app.ai.approval_draft import ApprovalDraftCandidate, ApprovalDraftProviderInput, DraftIntent

CORRECTION = re.compile(r"정정|수정|아니|말고|잘못|취소|바꿔|변경")
LABELED_INPUT = re.compile(
    r"(?m)^\s*(?:문서\s*유형|제목|개요|업무\s*내용|업무\s*기간|참여\s*인원|산출물)\s*[:：]"
)
SENTENCE_END = re.compile(r"[.!?。](?=\s+[가-힣A-Za-z])")
FIELD_PATTERNS = (
    ("업무 기간", re.compile(r"^(?:업무\s*기간|기간)(?:은|는|이|가|\s*[:：])")),
    ("주요 산출물", re.compile(r"^(?:주요\s*)?(?:산출물|결과물)(?:은|는|이|가|\s*[:：])")),
    ("참여 인원", re.compile(r"^(?:참여\s*인원|참여자|참석자)(?:은|는|이|가|\s*[:：])")),
)


@dataclass(frozen=True)
class NaturalFact:
    field: str
    text: str
    draft_text: str
    source_index: int
    start: int
    end: int
    transformation: str


@dataclass(frozen=True)
class NaturalGeneralResult:
    candidate: ApprovalDraftCandidate
    facts: list[NaturalFact]
    example_title: str | None


def _spans(source: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    offset = 0
    for segment in source.splitlines(keepends=True):
        line = segment.rstrip("\r\n")
        start = 0
        ends = [match.end() for match in SENTENCE_END.finditer(line)] + [len(line)]
        for end in ends:
            raw = line[start:end]
            left = len(raw) - len(raw.lstrip())
            right = len(raw.rstrip())
            if left < right:
                spans.append((offset + start + left, offset + start + right))
            start = end
        offset += len(segment)
    return spans


def _polite(text: str) -> tuple[str, str]:
    # Preserve negation, subject, numbers and all other words. Questions are unchanged.
    match = re.fullmatch(r"(.*?)(했어요|했어)([.。]?)", text)
    if match:
        return f"{match.group(1)}했습니다{match.group(3)}", "POLITE_PAST"
    # "아니야" is not a copula and must not be mistaken for a positive statement.
    if re.search(r"아니야[.。]?$", text):
        return text, "EXACT"
    match = re.fullmatch(r"(.*?)(이야|이에요)([.。]?)", text)
    if match and match.group(1):
        return f"{match.group(1)}입니다{match.group(3)}", "POLITE_COPULA"
    return text, "EXACT"


def natural_general_draft(
    candidate: ApprovalDraftCandidate,
    original: ApprovalDraftProviderInput,
    examples: list[tuple[str, list[str]]],
) -> NaturalGeneralResult | None:
    if candidate.intent != DraftIntent.GENERAL:
        return None
    # Conflicting follow-ups cannot be resolved by concatenation or by the model.
    if any(CORRECTION.search(answer) for answer in original.answers):
        return None
    if any(LABELED_INPUT.search(text) for text in [original.request, *original.answers]):
        return None
    facts: list[NaturalFact] = []
    for source_index, source in enumerate([original.request, *original.answers]):
        for start, end in _spans(source):
            text = source[start:end]
            field = next(
                (name for name, pattern in FIELD_PATTERNS if pattern.match(text)), "업무 내용"
            )
            draft_text, transformation = _polite(text)
            facts.append(
                NaturalFact(field, text, draft_text, source_index, start, end, transformation)
            )
    if not facts or len(facts) > 128:
        return None
    # Multiple different values for the same explicit field may be corrections;
    # do not decide which one supersedes the other.
    for field, _ in FIELD_PATTERNS:
        values = {fact.text for fact in facts if fact.field == field}
        if len(values) > 1:
            return None
    # Never reorder or omit spans; section headers only mark consecutive spans.
    parts: list[str] = []
    previous_field: str | None = None
    section = 0
    for fact in facts:
        if fact.field != previous_field:
            section += 1
            parts.append(f"{section}. {fact.field}")
            previous_field = fact.field
        parts.append(fact.draft_text)
    content = "\n".join(parts)
    if len(content) > 5000:
        return None
    result = ApprovalDraftCandidate(intent=DraftIntent.GENERAL, title="업무 기안", content=content)
    title, outline = examples[0] if examples else (None, [])
    used = bool(title and any(fact.field in outline for fact in facts))
    return NaturalGeneralResult(result, facts, title if used else None)

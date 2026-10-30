"""Assemble a bounded general draft from explicit, individually traceable facts.

The model cannot supply values, connective claims, or arbitrary headings. User text is
never passed to this module's example selector; examples contain server-owned headings.
"""

import re
from dataclasses import dataclass

from app.ai.approval_draft import ApprovalDraftCandidate, ApprovalDraftProviderInput, DraftIntent

# Only equivalences whose meaning does not imply that an action happened are allowed.
HEADINGS: dict[str, tuple[str, ...]] = {
    "개요": ("개요",),
    "배경": ("배경",),
    "업무 내용": ("업무 내용",),
    "업무 기간": ("업무 기간",),
    "주요 산출물": ("주요 산출물",),
    "참여 인원": ("참여 인원",),
    "요청 사항": ("요청 사항",),
}
# Fixed introductions do not claim that a document exists or an action was completed.
INTRODUCTIONS = {
    "업무 기간": "업무 기간은 다음과 같습니다.",
    "주요 산출물": "주요 산출물은 다음과 같습니다.",
    "참여 인원": "참여 인원은 다음과 같습니다.",
}

ALIASES = {
    "제목": "제목",
    "문서 유형": "문서 유형",
    "개요": "개요",
    "배경": "배경",
    "업무 내용": "업무 내용",
    "업무내용": "업무 내용",
    "업무 기간": "업무 기간",
    "업무기간": "업무 기간",
    "기간": "업무 기간",
    "주요 산출물": "주요 산출물",
    "산출물": "주요 산출물",
    "참여 인원": "참여 인원",
    "참여자": "참여 인원",
    "요청 사항": "요청 사항",
}
LINE = re.compile(r"^\s*([^:：\n]{1,20})\s*[:：]\s*(.*?)\s*$")


@dataclass(frozen=True)
class Fact:
    field: str
    value: str
    source_index: int
    start: int
    end: int


@dataclass(frozen=True)
class GroundedGeneralResult:
    candidate: ApprovalDraftCandidate
    facts: list[Fact]
    example_title: str | None
    missing_fields: list[str]


def structured_general_draft(
    candidate: ApprovalDraftCandidate,
    original: ApprovalDraftProviderInput,
    examples: list[tuple[str, list[str]]],
) -> GroundedGeneralResult | None:
    """Require fully labelled single-line facts and reject ambiguity or duplicate fields."""
    facts: list[Fact] = []
    seen: set[str] = set()
    explicit_general = False
    for source_index, source in enumerate([original.request, *original.answers]):
        offset = 0
        for segment in source.splitlines(keepends=True):
            line = segment.rstrip("\r\n")
            if not line.strip():
                offset += len(segment)
                continue
            match = LINE.fullmatch(line)
            if match is None:
                return None
            key = ALIASES.get(match.group(1).strip())
            value = match.group(2)
            if key is None or not value or key in seen:
                return None
            seen.add(key)
            if key == "문서 유형":
                if value != "일반":
                    return None
                explicit_general = True
            else:
                facts.append(
                    Fact(key, value, source_index, offset + match.start(2), offset + match.end(2))
                )
            offset += len(segment)
    if candidate.intent != DraftIntent.GENERAL and not explicit_general:
        return None
    body = [fact for fact in facts if fact.field != "제목"]
    if len(body) < 2:
        return None
    title = next((fact.value for fact in facts if fact.field == "제목"), "업무 기안")
    if len(title) > 120:
        return None
    # Use one retrieved example for heading names only. Never treat its content as fact.
    example_title, outline = examples[0] if examples else (None, [])
    parts: list[str] = []
    used_example = False
    for number, fact in enumerate(body, 1):
        options = HEADINGS[fact.field]
        heading = next((name for name in options if name in outline), options[0])
        used_example |= heading in outline
        intro = INTRODUCTIONS.get(fact.field)
        body_text = f"{intro}\n{fact.value}" if intro else fact.value
        parts.append(f"{number}. {heading}\n{body_text}")
    content = "\n\n".join(parts)
    if len(content) > 5000:
        return None
    # Construct a fresh candidate so no model-supplied value or sentence survives.
    result = ApprovalDraftCandidate(intent=DraftIntent.GENERAL, title=title, content=content)
    mentioned = {fact.field for fact in body}
    missing = [heading for heading in outline if heading in HEADINGS and heading not in mentioned]
    return GroundedGeneralResult(
        result, facts, example_title if used_example else None, missing if used_example else []
    )

"""Fail-closed textual correspondence for general draft content."""

from app.ai.approval_draft import ApprovalDraftCandidate, ApprovalDraftProviderInput, DraftIntent
from app.core.errors import DomainValidationError


def verify_general_draft(
    candidate: ApprovalDraftCandidate, original: ApprovalDraftProviderInput
) -> tuple[ApprovalDraftCandidate, str]:
    if candidate.intent != DraftIntent.GENERAL:
        return candidate, "NOT_APPLICABLE"
    # General drafts have no structured financial or trip facts. Do not expose
    # unverified model values through preview.amount or the candidate response.
    candidate = candidate.model_copy(
        update={
            field: None
            for field in (
                "amount",
                "destination",
                "start_date",
                "end_date",
                "transportation",
                "lodging",
                "meals",
                "other",
                "client_name",
                "visit_purpose",
                "expense_date",
                "merchant",
                "expense_category",
                "expense_purpose",
                "receipt_reference",
            )
        }
    )
    sources = [original.request, *original.answers]
    source_lines = [
        line.strip() for source in sources for line in source.splitlines() if line.strip()
    ]
    content_lines = [
        line.strip() for line in (candidate.content or "").splitlines() if line.strip()
    ]
    # Keep all lines in order: accepting partial substrings or generated headings can
    # omit a negation or imply a decision not stated by the user.
    if candidate.title in source_lines and content_lines == source_lines:
        return candidate, "INPUT_MATCHED"
    content = "\n\n".join(sources)
    if len(content) > 5000:
        raise DomainValidationError("DRAFT_INPUT_TOO_LONG", "Draft input exceeds 5000 characters")
    return candidate.model_copy(
        update={"title": "업무 기안", "content": content}
    ), "REBUILT_FROM_INPUT"

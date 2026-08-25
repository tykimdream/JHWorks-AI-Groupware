from datetime import date, datetime
from enum import StrEnum

from pydantic import Field

from app.ai.approval_draft import DraftIntent
from app.core.schema import ApiSchema
from app.schemas.approval import ApprovalCreate
from app.schemas.policy import PolicySearchResponse


class ApprovalDraftAIStatus(StrEnum):
    NEEDS_INPUT = "NEEDS_INPUT"
    PREVIEW = "PREVIEW"
    UNSUPPORTED = "UNSUPPORTED"


class ApprovalDraftPrepareRequest(ApiSchema):
    request: str = Field(min_length=2, max_length=2000)
    answers: list[str] = Field(default_factory=list, max_length=8)


class ApprovalDraftCandidateRead(ApiSchema):
    intent: DraftIntent
    title: str | None
    content: str | None
    amount: int | None
    destination: str | None
    start_date: date | None
    end_date: date | None
    transportation: int | None
    lodging: int | None
    meals: int | None
    other: int | None
    client_name: str | None
    visit_purpose: str | None


class ApprovalDraftQuestion(ApiSchema):
    field: str
    prompt: str


class ApprovalDraftUsage(ApiSchema):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class ApprovalDraftPrepareResponse(ApiSchema):
    status: ApprovalDraftAIStatus
    assistant_message: str
    candidate: ApprovalDraftCandidateRead
    missing_fields: list[str]
    questions: list[ApprovalDraftQuestion]
    preview: ApprovalCreate | None
    confirmation_token: str | None
    policy_context: PolicySearchResponse
    provider: str
    model: str
    prompt_version: str
    usage: ApprovalDraftUsage
    latency_ms: int = Field(ge=0)
    generated_at: datetime


class ApprovalDraftConfirmRequest(ApiSchema):
    preview: ApprovalCreate
    confirmation_token: str = Field(min_length=1)

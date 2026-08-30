from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import Field

from app.ai.leave_assistant import LeaveAssistantIntent
from app.core.schema import ApiSchema
from app.schemas.attendance import LeaveAvailabilityRead
from app.schemas.policy import PolicySearchResponse


class LeaveAssistantStatus(StrEnum):
    NEEDS_INPUT = "NEEDS_INPUT"
    READY = "READY"
    UNSUPPORTED = "UNSUPPORTED"


class LeaveAssistantRequest(ApiSchema):
    request: str = Field(min_length=2, max_length=2000)
    answers: list[str] = Field(default_factory=list, max_length=8)


class LeaveAssistantQuestion(ApiSchema):
    field: str
    prompt: str


class LeaveAssistantQuery(ApiSchema):
    intent: LeaveAssistantIntent
    search_start: date | None
    search_end: date | None
    requested_days: Decimal | None


class LeaveAssistantUsage(ApiSchema):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class LeaveAssistantResponse(ApiSchema):
    status: LeaveAssistantStatus
    assistant_message: str
    query: LeaveAssistantQuery
    missing_fields: list[str]
    questions: list[LeaveAssistantQuestion]
    availability: LeaveAvailabilityRead | None
    policy_context: PolicySearchResponse
    provider: str
    model: str
    prompt_version: str
    usage: LeaveAssistantUsage
    latency_ms: int = Field(ge=0)
    generated_at: datetime

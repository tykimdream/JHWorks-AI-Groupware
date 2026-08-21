from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.ai.approval_review import ReviewCategory, ReviewField, ReviewSeverity
from app.core.schema import ApiSchema


class ReviewSource(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"


class ReviewStatus(StrEnum):
    PASS = "PASS"
    NEEDS_REVISION = "NEEDS_REVISION"


class AIReviewRequest(ApiSchema):
    version: int = Field(ge=1)


class AIReviewIssue(ApiSchema):
    code: str = Field(min_length=1, max_length=64)
    source: ReviewSource
    severity: ReviewSeverity
    category: ReviewCategory
    field: ReviewField
    message: str = Field(min_length=1, max_length=500)
    suggestion: str | None = Field(default=None, max_length=1000)


class AIReviewUsage(ApiSchema):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class AIReviewResponse(ApiSchema):
    approval_id: str
    approval_version: int
    current_approval_version: int
    is_stale: bool
    status: ReviewStatus
    score: int = Field(ge=0, le=100)
    issues: list[AIReviewIssue]
    revised_content: str | None
    provider: str
    model: str
    prompt_version: str
    usage: AIReviewUsage
    latency_ms: int = Field(ge=0)
    reviewed_at: datetime

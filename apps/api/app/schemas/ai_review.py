from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.ai.approval_review import ReviewCategory, ReviewField, ReviewSeverity
from app.core.schema import ApiSchema
from app.schemas.policy import (
    PolicyCitation,
    PolicyEmbeddingUsage,
    PolicyRetrievalStatus,
)


class ReviewSource(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"
    POLICY = "POLICY"


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
    citations: list[PolicyCitation] = Field(default_factory=list, max_length=3)


class AIReviewUsage(ApiSchema):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class PolicyReviewMetadata(ApiSchema):
    status: PolicyRetrievalStatus
    retrieved_citations: list[PolicyCitation]
    provider: str | None
    model: str | None
    usage: PolicyEmbeddingUsage
    latency_ms: int = Field(ge=0)


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
    policy_review: PolicyReviewMetadata
    latency_ms: int = Field(ge=0)
    reviewed_at: datetime

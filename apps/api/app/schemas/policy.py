from datetime import date, datetime
from enum import StrEnum

from pydantic import Field

from app.core.schema import ApiSchema
from app.models.enums import PolicyType


class PolicySectionRead(ApiSchema):
    section_id: str
    title: str
    content: str
    order: int


class PolicyRead(ApiSchema):
    id: str
    type: PolicyType
    title: str
    version: str
    effective_from: date
    content_hash: str
    published_at: datetime | None
    sections: list[PolicySectionRead]


class PolicyRetrievalStatus(StrEnum):
    READY = "READY"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_INDEXED = "NOT_INDEXED"
    UNAVAILABLE = "UNAVAILABLE"


class PolicySearchRequest(ApiSchema):
    query: str = Field(min_length=2, max_length=2000)
    policy_type: PolicyType | None = None
    top_k: int | None = Field(default=None, ge=1, le=10)


class PolicyCitation(ApiSchema):
    citation_key: str
    policy_id: str
    policy_title: str
    policy_type: PolicyType
    version: str
    section_id: str
    section_title: str
    excerpt: str
    similarity_score: float = Field(ge=-1.0, le=1.0)


class PolicyEmbeddingUsage(ApiSchema):
    input_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class PolicySearchResponse(ApiSchema):
    status: PolicyRetrievalStatus
    items: list[PolicyCitation]
    provider: str | None
    model: str | None
    usage: PolicyEmbeddingUsage
    latency_ms: int = Field(ge=0)

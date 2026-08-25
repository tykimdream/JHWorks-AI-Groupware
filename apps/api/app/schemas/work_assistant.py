from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.schema import ApiSchema
from app.schemas.policy import PolicyCitation


class WorkAssistantRequest(ApiSchema):
    message: str = Field(min_length=2, max_length=2000)


class WorkAssistantToolExecution(ApiSchema):
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


class WorkAssistantUsage(ApiSchema):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class WorkAssistantResponse(ApiSchema):
    answer: str
    tool_executions: list[WorkAssistantToolExecution]
    policy_citations: list[PolicyCitation]
    provider: str
    model: str
    prompt_version: str
    round_count: int = Field(ge=1, le=3)
    usage: WorkAssistantUsage
    latency_ms: int = Field(ge=0)
    answered_at: datetime

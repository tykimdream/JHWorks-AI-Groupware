"""Public, content-free diagnostics; stage success is not factual correctness."""

from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.ai.approval_draft import PROMPT_VERSION
from app.core.schema import ApiSchema


class DraftStage(StrEnum):
    INPUT = "input"
    PROVIDER = "provider"
    NORMALIZE = "normalize"
    VALIDATE = "validate"
    POLICY = "policy"
    PREVIEW = "preview"


class DraftStageOutcome(StrEnum):
    PASSED = "PASSED"
    NEEDS_INPUT = "NEEDS_INPUT"
    UNSUPPORTED = "UNSUPPORTED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    FAILED = "FAILED"


class DraftStageRecord(ApiSchema):
    stage: DraftStage
    outcome: DraftStageOutcome
    duration_ms: int = Field(ge=0)


class DraftExecutionRead(ApiSchema):
    run_id: str
    harness_version: Literal["draft-harness-v1"] = "draft-harness-v1"
    prompt_version: str = PROMPT_VERSION
    provider: str | None = None
    model: str | None = None
    outcome: Literal["PREVIEW", "NEEDS_INPUT", "UNSUPPORTED", "FAILED"]
    stages: list[DraftStageRecord]
    duration_ms: int = Field(ge=0)

from typing import Literal

from pydantic import Field

from app.core.schema import ApiSchema
from app.schemas.employee import CurrentEmployeeRead


class AICapabilities(ApiSchema):
    approval_draft: bool = False
    approval_review: bool = False
    leave_assistant: bool = False
    work_assistant: bool = False
    policy_embedding: bool = False


class DemoConfiguration(ApiSchema):
    ai_capabilities: AICapabilities = Field(default_factory=AICapabilities)
    expense_ai_request_limit: int | None = None
    enabled: bool
    duration_minutes: int
    write_limit: int = 20
    request_limit: int = 100


class DemoRoleRequest(ApiSchema):
    role: Literal["author", "manager"]


class DemoVisitRead(ApiSchema):
    employee: CurrentEmployeeRead
    expires_at_epoch: int

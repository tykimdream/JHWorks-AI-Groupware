from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import Field

from app.core.schema import ApiSchema
from app.models.enums import LeaveAgentStatus
from app.schemas.approval import ApprovalRead
from app.schemas.attendance import LeaveAvailabilityReasonRead
from app.schemas.leave_assistant import LeaveAssistantResponse
from app.schemas.leave_draft_tool import (
    LeaveDraftConfirmRequest,
    LeaveDraftPrepareRequest,
    LeaveDraftPrepareResponse,
)


class LeaveAgentTraceRead(ApiSchema):
    at: datetime
    from_status: LeaveAgentStatus | None
    to_status: LeaveAgentStatus
    event: str
    result_code: str


class LeaveAgentRunRead(ApiSchema):
    id: str
    status: LeaveAgentStatus
    approval_id: str | None
    retry_count: int
    last_error_code: str | None
    version: int
    trace: list[LeaveAgentTraceRead]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class LeaveAgentStartRequest(ApiSchema):
    request: str = Field(min_length=2, max_length=2000)
    answers: list[str] = Field(default_factory=list, max_length=8)


class LeaveAgentAnswerRequest(ApiSchema):
    answer: str = Field(min_length=1, max_length=2000)


class LeaveAgentConsultationRead(ApiSchema):
    run: LeaveAgentRunRead
    consultation: LeaveAssistantResponse | None


class LeaveAgentDraftPrepareRead(ApiSchema):
    run: LeaveAgentRunRead
    preparation: LeaveDraftPrepareResponse


class LeaveAgentDraftConfirmRead(ApiSchema):
    run: LeaveAgentRunRead
    approval: ApprovalRead


class LeaveSubmitPreview(ApiSchema):
    approval_id: str
    approval_version: int = Field(ge=1)
    requested_days: Decimal
    available_days: Decimal
    pending_days: Decimal
    account_version: int = Field(ge=1)
    manager_id: str
    manager_name: str
    manager_position: str
    warnings: list[LeaveAvailabilityReasonRead]
    calendar_fingerprint: str


class LeaveSubmitPrepareRequest(ApiSchema):
    approval_version: int = Field(ge=1)


class LeaveSubmitPrepareRead(ApiSchema):
    run: LeaveAgentRunRead
    preview: LeaveSubmitPreview
    confirmation_token: str
    expires_at: datetime


class LeaveSubmitDecision(StrEnum):
    CONFIRM = "CONFIRM"
    CANCEL = "CANCEL"


class LeaveSubmitResumeRequest(ApiSchema):
    decision: LeaveSubmitDecision
    preview: LeaveSubmitPreview
    confirmation_token: str = Field(min_length=1)


class LeaveSubmitResumeRead(ApiSchema):
    run: LeaveAgentRunRead
    approval: ApprovalRead


LeaveAgentDraftPreparePayload = LeaveDraftPrepareRequest
LeaveAgentDraftConfirmPayload = LeaveDraftConfirmRequest

from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.core.schema import ApiSchema
from app.schemas.approval import ApprovalCreate
from app.schemas.attendance import (
    LeaveAvailabilityCandidateRead,
    LeaveAvailabilityReasonRead,
)
from app.schemas.policy import PolicySearchResponse


class LeaveDraftApproverRead(ApiSchema):
    id: str
    name: str
    position: str


class LeaveDraftPrepareRequest(ApiSchema):
    candidate: LeaveAvailabilityCandidateRead
    leave_unit: Literal["FULL_DAY", "HALF_DAY_AM", "HALF_DAY_PM"] = "FULL_DAY"


class LeaveDraftExactPreview(ApiSchema):
    approval: ApprovalCreate
    candidate: LeaveAvailabilityCandidateRead
    requested_days: Decimal
    leave_unit: Literal["FULL_DAY", "HALF_DAY_AM", "HALF_DAY_PM"]
    available_days: Decimal
    account_version: int = Field(ge=1)
    manager: LeaveDraftApproverRead
    policy_context: PolicySearchResponse
    warnings: list[LeaveAvailabilityReasonRead]
    calendar_fingerprint: str
    policy_fingerprint: str


class LeaveDraftPrepareResponse(ApiSchema):
    preview: LeaveDraftExactPreview
    confirmation_token: str


class LeaveDraftConfirmRequest(ApiSchema):
    preview: LeaveDraftExactPreview
    confirmation_token: str = Field(min_length=1)

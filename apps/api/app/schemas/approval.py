from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.core.schema import ApiSchema
from app.models.enums import ApprovalLineStatus, ApprovalStatus, ApprovalType
from app.schemas.employee import EmployeeSummary


class AttachmentMetadata(ApiSchema):
    name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)


class GeneralDetails(ApiSchema):
    kind: Literal["GENERAL"] = "GENERAL"


class CostBreakdown(ApiSchema):
    transportation: int | None = Field(default=None, ge=0)
    lodging: int | None = Field(default=None, ge=0)
    meals: int | None = Field(default=None, ge=0)
    other: int | None = Field(default=None, ge=0)


class BusinessTripDetails(ApiSchema):
    kind: Literal["BUSINESS_TRIP"] = "BUSINESS_TRIP"
    destination: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    cost_breakdown: CostBreakdown | None = None
    client_name: str | None = Field(default=None, max_length=200)
    visit_purpose: str | None = Field(default=None, max_length=1000)


class LeaveDetails(ApiSchema):
    kind: Literal["LEAVE"] = "LEAVE"
    leave_type: Literal["ANNUAL"] = "ANNUAL"
    leave_unit: Literal["FULL_DAY", "HALF_DAY_AM", "HALF_DAY_PM"] = "FULL_DAY"
    start_date: date | None = None
    end_date: date | None = None
    requested_days: Decimal | None = Field(default=None, ge=Decimal("0.5"), decimal_places=1)
    reason: str | None = Field(default=None, max_length=1000)
    handover_note: str | None = Field(default=None, max_length=2000)


ApprovalDetails = Annotated[
    GeneralDetails | BusinessTripDetails | LeaveDetails,
    Field(discriminator="kind"),
]


class ApprovalDraftFields(ApiSchema):
    type: ApprovalType
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(default="", max_length=5000)
    amount: int | None = Field(default=None, ge=0)
    details: ApprovalDetails
    attachment_metadata: list[AttachmentMetadata] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def details_match_type(self) -> "ApprovalDraftFields":
        if self.type.value != self.details.kind:
            raise ValueError("details.kind must match approval type")
        return self


class ApprovalCreate(ApprovalDraftFields):
    pass


class ApprovalUpdate(ApprovalDraftFields):
    version: int = Field(ge=1)


class ApprovalCommand(ApiSchema):
    version: int = Field(ge=1)


class ApprovalDecision(ApprovalCommand):
    comment: str | None = Field(default=None, max_length=2000)


class ApprovalLineRead(ApiSchema):
    id: str
    step: int
    round: int
    approver: EmployeeSummary
    status: ApprovalLineStatus
    comment: str | None
    acted_at: datetime | None


class ApprovalRead(ApiSchema):
    id: str
    type: ApprovalType
    title: str
    content: str
    author: EmployeeSummary
    status: ApprovalStatus
    amount: int | None
    details: ApprovalDetails
    attachment_metadata: list[AttachmentMetadata]
    version: int
    submitted_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime
    lines: list[ApprovalLineRead]


class ApprovalListResponse(ApiSchema):
    items: list[ApprovalRead]
    total: int

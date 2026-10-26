from typing import Annotated

from pydantic import Field

from app.core.schema import ApiSchema
from app.schemas.approval import ApprovalCommand, ApprovalCreate
from app.schemas.approval_draft_ai import ApprovalDraftPrepareResponse
from app.schemas.expense_checks import ExpenseChecks
from app.schemas.expense_policy import ExpensePolicyValidation


class ExpenseRevisionRequest(ApprovalCommand):
    answers: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(
        default_factory=list, max_length=8
    )


class ExpenseChange(ApiSchema):
    field: str
    before: str | int | None
    after: str | int | None


class ExpenseRevisionResponse(ApiSchema):
    approval_id: str
    version: int
    rejection_comment: str
    prepared: ApprovalDraftPrepareResponse
    changes: list[ExpenseChange]
    apply_token: str | None


class ExpenseRevisionApply(ApprovalCommand):
    preview: ApprovalCreate
    apply_token: str = Field(min_length=1, max_length=5000)


class ExpenseDecisionBrief(ApiSchema):
    approval_id: str
    version: int
    checks: ExpenseChecks
    policy: ExpensePolicyValidation
    rejection_comment: str | None
    receipt_reference: str | None

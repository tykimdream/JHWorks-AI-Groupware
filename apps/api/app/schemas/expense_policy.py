from typing import Literal

from app.core.schema import ApiSchema
from app.schemas.policy import PolicyCitation


class ExpenseRuleCheck(ApiSchema):
    citation_key: str
    code: str
    outcome: Literal["ACTION_REQUIRED", "NOT_APPLICABLE", "NOT_EVALUATED"]
    message: str


class ExpensePolicyValidation(ApiSchema):
    status: Literal["CATALOG_CHECKED", "UNAVAILABLE"]
    fingerprint: str
    retrieval_checked: bool
    citations: list[PolicyCitation]
    checks: list[ExpenseRuleCheck]

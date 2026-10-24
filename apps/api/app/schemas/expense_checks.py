from datetime import datetime

from app.core.schema import ApiSchema
from app.models.enums import ApprovalStatus


class ExpenseMatch(ApiSchema):
    id: str
    title: str
    status: ApprovalStatus


class ExpenseChecks(ApiSchema):
    approval_id: str
    approval_title: str
    version: int
    missing_fields: list[str]
    duplicate_matches: list[ExpenseMatch]
    more_matches: bool = False
    checked_at: datetime


class ExpenseInsights(ApiSchema):
    items: list[ExpenseChecks]
    checked_count: int
    has_more_documents: bool
    checked_at: datetime

from typing import Literal

from app.core.schema import ApiSchema


class ExpenseFieldCheck(ApiSchema):
    field: str
    status: Literal["INPUT_MATCHED", "MISSING", "UNVERIFIED"]
    source_index: int | None = None
    start: int | None = None
    end: int | None = None


class ExpenseGroundingRead(ApiSchema):
    version: Literal["expense-input-grounding-v1"] = "expense-input-grounding-v1"
    status: Literal["INPUT_MATCHED", "NEEDS_INPUT", "NOT_APPLICABLE"]
    checks: list[ExpenseFieldCheck]

from typing import Literal

from app.core.schema import ApiSchema
from app.models.enums import ApprovalStatus


class ExpenseGuideField(ApiSchema):
    field: str
    label: str
    description: str
    example: str
    required: bool


class ExpenseGuideStage(ApiSchema):
    status: ApprovalStatus
    title: str
    meaning: str
    next_step: str


class ExpenseGuideAnswer(ApiSchema):
    id: str
    question: str
    answer: str


class ExpenseGuide(ApiSchema):
    version: Literal["expense-guide-v1"] = "expense-guide-v1"
    source: str = "경비 제출 검사와 전자결재 상태 전이 계약"
    fields: list[ExpenseGuideField]
    stages: list[ExpenseGuideStage]
    questions: list[ExpenseGuideAnswer]

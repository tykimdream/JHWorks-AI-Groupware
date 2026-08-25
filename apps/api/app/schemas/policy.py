from datetime import date, datetime

from app.core.schema import ApiSchema
from app.models.enums import PolicyType


class PolicySectionRead(ApiSchema):
    section_id: str
    title: str
    content: str
    order: int


class PolicyRead(ApiSchema):
    id: str
    type: PolicyType
    title: str
    version: str
    effective_from: date
    content_hash: str
    published_at: datetime | None
    sections: list[PolicySectionRead]

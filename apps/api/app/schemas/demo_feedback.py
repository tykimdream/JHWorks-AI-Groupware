import re
from typing import Literal

from pydantic import Field, field_validator

from app.core.schema import ApiSchema


class DemoFeedbackCreate(ApiSchema):
    category: Literal["usability", "bug", "idea"]
    screen: Literal["approvals", "attendance", "assistant", "general"]
    message: str = Field(min_length=10, max_length=1000)
    consent: Literal[True]

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Please provide at least 10 meaningful characters")
        if re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|sk-[A-Za-z0-9_-]{12,}|Bearer\s+\S+", value):
            raise ValueError("Do not include email addresses or credentials")
        return value


class DemoFeedbackReceipt(ApiSchema):
    id: str
    status: Literal["received"] = "received"

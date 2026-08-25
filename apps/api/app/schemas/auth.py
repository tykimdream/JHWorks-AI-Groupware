from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, Field

from app.core.schema import ApiSchema
from app.schemas.employee import CurrentEmployeeRead


def validate_demo_email(value: str) -> str:
    normalized = value.strip().lower()
    try:
        result = validate_email(
            normalized,
            check_deliverability=False,
            test_environment=normalized.endswith("@jhworks.test"),
        )
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc
    return result.normalized


DemoEmail = Annotated[str, AfterValidator(validate_demo_email)]


class LoginRequest(ApiSchema):
    email: DemoEmail
    password: str = Field(min_length=8, max_length=128)


class LoginResponse(ApiSchema):
    employee: CurrentEmployeeRead


class LogoutResponse(ApiSchema):
    success: bool

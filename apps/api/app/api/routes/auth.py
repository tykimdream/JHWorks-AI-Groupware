from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.dependencies import DbSession
from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.core.security import create_session_token, verify_password
from app.models.employee import Employee
from app.schemas.auth import LoginRequest, LoginResponse, LogoutResponse
from app.services.mappers import current_employee_read

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: DbSession) -> LoginResponse:
    employee = db.scalar(
        select(Employee)
        .options(
            joinedload(Employee.credential),
            joinedload(Employee.department),
            joinedload(Employee.manager),
        )
        .where(Employee.email == payload.email.lower())
    )
    if (
        employee is None
        or employee.credential is None
        or not employee.is_active
        or not verify_password(payload.password, employee.credential.password_hash)
    ):
        raise AuthenticationError("The email or password is incorrect")

    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_session_token(employee.id),
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        path="/",
    )
    return LoginResponse(employee=current_employee_read(employee))


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response) -> LogoutResponse:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    return LogoutResponse(success=True)

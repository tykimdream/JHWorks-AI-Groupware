from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AuthenticationError
from app.core.security import decode_session_token
from app.models.employee import Employee

DbSession = Annotated[Session, Depends(get_db)]


def get_current_employee(
    db: DbSession,
    session_token: Annotated[str | None, Cookie(alias=get_settings().session_cookie_name)] = None,
) -> Employee:
    if session_token is None:
        raise AuthenticationError()

    employee_id = decode_session_token(session_token)
    employee = db.scalar(
        select(Employee)
        .options(joinedload(Employee.department), joinedload(Employee.manager))
        .where(Employee.id == employee_id)
    )
    if employee is None or not employee.is_active:
        raise AuthenticationError("The employee account is unavailable")
    return employee


CurrentEmployee = Annotated[Employee, Depends(get_current_employee)]

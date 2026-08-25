from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentEmployee, DbSession
from app.core.errors import DomainValidationError
from app.schemas.attendance import AttendanceOverviewRead
from app.services import attendance as attendance_service

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("/overview", response_model=AttendanceOverviewRead)
def attendance_overview(
    db: DbSession,
    current_employee: CurrentEmployee,
    start_date: Annotated[date, Query(alias="startDate")],
    end_date: Annotated[date, Query(alias="endDate")],
) -> AttendanceOverviewRead:
    if end_date < start_date:
        raise DomainValidationError(
            "INVALID_DATE_RANGE",
            "endDate must be on or after startDate",
        )
    if (end_date - start_date).days > 92:
        raise DomainValidationError(
            "DATE_RANGE_TOO_LARGE",
            "Attendance overview supports a maximum range of 93 days",
        )
    return attendance_service.get_attendance_overview(
        db,
        current_employee,
        start_date,
        end_date,
    )

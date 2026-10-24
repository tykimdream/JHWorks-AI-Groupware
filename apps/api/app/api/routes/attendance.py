from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentEmployee, DbSession
from app.core.errors import DomainValidationError
from app.schemas.attendance import AttendanceOverviewRead, LeaveAvailabilityRead
from app.services import attendance as attendance_service
from app.services import leave_availability as leave_availability_service

router = APIRouter(prefix="/attendance", tags=["근태·휴가"])


@router.get("/overview", response_model=AttendanceOverviewRead, summary="근태 일정·연차 현황 조회")
def attendance_overview(
    db: DbSession,
    current_employee: CurrentEmployee,
    start_date: Annotated[date, Query(alias="startDate")],
    end_date: Annotated[date, Query(alias="endDate")],
) -> AttendanceOverviewRead:
    """
    선택한 기간의 회사·부서·팀 일정과 내 연차 현황을 조회합니다. 한
    번에 최대 93일을 조회할 수 있습니다.
    """
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


@router.get("/leave-availability", response_model=LeaveAvailabilityRead, summary="휴가 가능일 조회")
def leave_availability(
    db: DbSession,
    current_employee: CurrentEmployee,
    start_date: Annotated[date, Query(alias="startDate")],
    end_date: Annotated[date, Query(alias="endDate")],
    requested_days: Annotated[
        Decimal,
        Query(alias="requestedDays", ge=Decimal("0.5"), le=Decimal("5.0")),
    ],
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> LeaveAvailabilityRead:
    """
    잔여 연차, 휴일과 업무 일정을 확인해 요청한 일수의 휴가 후보를
    반환합니다. 같은 연도 안에서 최대 93일을 검색합니다.
    """
    if end_date < start_date:
        raise DomainValidationError(
            "INVALID_DATE_RANGE",
            "endDate must be on or after startDate",
        )
    if (end_date - start_date).days > 92:
        raise DomainValidationError(
            "DATE_RANGE_TOO_LARGE",
            "Leave availability supports a maximum range of 93 days",
        )
    if start_date.year != end_date.year:
        raise DomainValidationError(
            "CROSS_YEAR_RANGE_NOT_SUPPORTED",
            "Leave availability must be searched within one calendar year",
        )
    if requested_days != Decimal("0.5") and requested_days != requested_days.to_integral():
        raise DomainValidationError(
            "UNSUPPORTED_LEAVE_DURATION",
            "requestedDays must be 0.5 or a whole number of days",
        )
    return leave_availability_service.find_leave_availability(
        db,
        current_employee,
        start_date,
        end_date,
        requested_days,
        limit,
    )

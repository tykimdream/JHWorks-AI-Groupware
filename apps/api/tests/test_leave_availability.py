from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.attendance import LeaveAccount, WorkCalendarEvent
from app.models.enums import (
    AttendanceEventCategory,
    AttendanceEventScope,
    AttendanceEventStatus,
    AttendanceImpact,
)


def _search(
    client: TestClient,
    start_date: str,
    end_date: str,
    requested_days: str = "2.0",
    limit: int = 5,
) -> Any:
    return client.get(
        "/api/v1/attendance/leave-availability",
        params={
            "startDate": start_date,
            "endDate": end_date,
            "requestedDays": requested_days,
            "limit": limit,
        },
    )


def test_availability_ranks_conflict_free_candidates_first(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "seojin.yoon@jhworks.test")

    response = _search(client, "2026-09-01", "2026-09-18")
    repeated = _search(client, "2026-09-01", "2026-09-18")

    assert response.status_code == 200, response.text
    result = response.json()
    assert result == repeated.json()
    assert result["status"] == "READY"
    assert result["leaveBalance"]["availableDays"] == "9.5"
    assert result["candidates"][0] == {
        "startDate": "2026-09-01",
        "endDate": "2026-09-02",
        "workDates": ["2026-09-01", "2026-09-02"],
        "requestedDays": "2.0",
        "status": "AVAILABLE",
        "reasons": [
            {
                "code": "NO_CONFLICT",
                "impact": "NONE",
                "message": "등록된 필수 일정이나 팀 휴가 충돌이 없습니다.",
                "eventIds": [],
            }
        ],
    }
    assert all(item["status"] == "AVAILABLE" for item in result["candidates"])


def test_company_event_and_team_leave_are_caution_candidates(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "seojin.yoon@jhworks.test")

    company_event = _search(client, "2026-09-02", "2026-09-04")
    team_leave = _search(client, "2026-09-14", "2026-09-15")

    assert company_event.status_code == 200
    company_candidate = company_event.json()["candidates"][0]
    assert company_candidate["status"] == "CAUTION"
    assert company_candidate["reasons"][0]["code"] == "COMPANY_EVENT"
    assert company_candidate["reasons"][0]["message"] == "JHWorks 전사 타운홀"

    assert team_leave.status_code == 200
    team_candidate = team_leave.json()["candidates"][0]
    assert team_candidate["status"] == "CAUTION"
    assert team_candidate["reasons"][0]["code"] == "TEAM_LEAVE"
    assert "하린" not in team_candidate["reasons"][0]["message"]
    assert "@" not in team_leave.text


def test_project_milestone_blocks_dates_and_holiday_is_skipped(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "seojin.yoon@jhworks.test")

    blocked = _search(client, "2026-09-10", "2026-09-11", "1.0")
    holiday = _search(client, "2026-09-23", "2026-09-28", "2.0")

    assert blocked.status_code == 200
    assert blocked.json()["status"] == "NO_CANDIDATE"
    assert all(not day["isSelectable"] for day in blocked.json()["days"])
    assert all(
        day["reasons"][0]["code"] == "PROJECT_MILESTONE"
        for day in blocked.json()["days"]
    )

    assert holiday.status_code == 200
    candidate = holiday.json()["candidates"][0]
    assert candidate["workDates"] == ["2026-09-23", "2026-09-28"]
    holiday_day = next(day for day in holiday.json()["days"] if day["date"] == "2026-09-24")
    assert holiday_day["isWorkday"] is False
    assert holiday_day["reasons"][0]["code"] == "HOLIDAY"


def test_half_day_candidate_and_existing_own_leave_block(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        db.add(
            WorkCalendarEvent(
                id="cal_leave_seojin_existing",
                category=AttendanceEventCategory.LEAVE,
                title="연차",
                start_date=date(2026, 9, 7),
                end_date=date(2026, 9, 7),
                scope=AttendanceEventScope.EMPLOYEE,
                employee_id="emp_sales_001",
                status=AttendanceEventStatus.TENTATIVE,
                impact=AttendanceImpact.CAUTION,
            )
        )
        db.commit()

    login(client, "seojin.yoon@jhworks.test")
    response = _search(client, "2026-09-07", "2026-09-08", "0.5")

    assert response.status_code == 200
    result = response.json()
    blocked_day = next(day for day in result["days"] if day["date"] == "2026-09-07")
    assert blocked_day["isSelectable"] is False
    assert blocked_day["reasons"][0]["code"] == "OWN_LEAVE"
    assert result["candidates"][0]["startDate"] == "2026-09-08"
    assert result["candidates"][0]["requestedDays"] == "0.5"


def test_insufficient_balance_and_missing_account_return_stable_status(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        account = db.scalar(
            select(LeaveAccount).where(
                LeaveAccount.employee_id == "emp_sales_001",
                LeaveAccount.year == 2026,
            )
        )
        assert account is not None
        account.used_days = Decimal("16.0")
        db.commit()

    login(client, "seojin.yoon@jhworks.test")
    insufficient = _search(client, "2026-09-01", "2026-09-10", "2.0")
    missing = _search(client, "2027-09-01", "2027-09-10", "1.0")

    assert insufficient.status_code == 200
    assert insufficient.json()["status"] == "INSUFFICIENT_BALANCE"
    assert insufficient.json()["candidates"] == []
    assert insufficient.json()["reasons"][0]["code"] == "INSUFFICIENT_BALANCE"
    assert missing.status_code == 200
    assert missing.json()["status"] == "ACCOUNT_UNAVAILABLE"
    assert missing.json()["leaveBalance"] is None


def test_availability_rejects_invalid_parameters_and_requires_login(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    unauthenticated = _search(client, "2026-09-01", "2026-09-10")
    assert unauthenticated.status_code == 401

    login(client, "seojin.yoon@jhworks.test")
    cross_year = _search(client, "2026-12-28", "2027-01-05")
    unsupported = _search(client, "2026-09-01", "2026-09-10", "1.5")
    too_large = _search(client, "2026-01-01", "2026-04-05")

    assert cross_year.status_code == 422
    assert cross_year.json()["error"]["code"] == "CROSS_YEAR_RANGE_NOT_SUPPORTED"
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_LEAVE_DURATION"
    assert too_large.status_code == 422
    assert too_large.json()["error"]["code"] == "DATE_RANGE_TOO_LARGE"

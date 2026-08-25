from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.attendance import LeaveAccount, WorkCalendarEvent
from app.scripts.seed import seed_database


def test_attendance_overview_returns_balance_and_relevant_schedule(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "seojin.yoon@jhworks.test")

    response = client.get(
        "/api/v1/attendance/overview",
        params={"startDate": "2026-09-01", "endDate": "2026-09-30"},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["rangeStart"] == "2026-09-01"
    assert result["rangeEnd"] == "2026-09-30"
    assert result["leaveBalances"] == [
        {
            "year": 2026,
            "grantedDays": "15.0",
            "carriedOverDays": "1.5",
            "usedDays": "7.0",
            "pendingDays": "0.0",
            "availableDays": "9.5",
            "version": 1,
            "updatedAt": result["leaveBalances"][0]["updatedAt"],
        }
    ]

    event_ids = {event["id"] for event in result["calendarEvents"]}
    assert "cal_company_townhall_20260903" in event_ids
    assert "cal_holiday_foundation_20260924" in event_ids
    assert "cal_sales_q3_review_20260910" in event_ids
    assert "cal_eng_release_20260916" not in event_ids

    team_leave_employees = {item["employee"]["id"] for item in result["teamLeaves"]}
    assert team_leave_employees == {"emp_sales_002", "emp_sales_mgr_001"}
    assert all("email" not in item["employee"] for item in result["teamLeaves"])


def test_attendance_overview_hides_other_department_schedule(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "garam.han@jhworks.test")

    response = client.get(
        "/api/v1/attendance/overview",
        params={"startDate": "2026-09-01", "endDate": "2026-09-30"},
    )

    assert response.status_code == 200
    result = response.json()
    event_ids = {event["id"] for event in result["calendarEvents"]}
    assert "cal_sales_q3_review_20260910" not in event_ids
    assert "cal_eng_release_20260916" not in event_ids
    assert result["teamLeaves"] == []


def test_attendance_overview_requires_authentication(client: TestClient) -> None:
    response = client.get(
        "/api/v1/attendance/overview",
        params={"startDate": "2026-09-01", "endDate": "2026-09-30"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_attendance_overview_rejects_invalid_or_large_range(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "seojin.yoon@jhworks.test")

    reversed_range = client.get(
        "/api/v1/attendance/overview",
        params={"startDate": "2026-09-30", "endDate": "2026-09-01"},
    )
    large_range = client.get(
        "/api/v1/attendance/overview",
        params={"startDate": "2026-01-01", "endDate": "2026-05-01"},
    )

    assert reversed_range.status_code == 422
    assert reversed_range.json()["error"]["code"] == "INVALID_DATE_RANGE"
    assert large_range.status_code == 422
    assert large_range.json()["error"]["code"] == "DATE_RANGE_TOO_LARGE"


def test_attendance_seed_is_idempotent(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        seed_database(db)
        seed_database(db)

        account_count = db.scalar(select(func.count()).select_from(LeaveAccount))
        event_count = db.scalar(select(func.count()).select_from(WorkCalendarEvent))

    assert account_count == 7
    assert event_count == 6

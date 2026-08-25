from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.attendance import LeaveAccount, WorkCalendarEvent
from app.models.enums import AttendanceEventStatus
from tests.test_approval_workflow import Login


def leave_payload(
    start_date: str = "2026-09-07",
    end_date: str = "2026-09-09",
    leave_unit: str = "FULL_DAY",
) -> dict[str, Any]:
    return {
        "type": "LEAVE",
        "title": "9월 연차 신청",
        "content": "개인 일정으로 연차 사용을 신청합니다.",
        "amount": None,
        "details": {
            "kind": "LEAVE",
            "leaveType": "ANNUAL",
            "leaveUnit": leave_unit,
            "startDate": start_date,
            "endDate": end_date,
            "requestedDays": "99.0",
            "reason": "개인 일정",
            "handoverNote": "고객 문의는 하린님에게 인계했습니다.",
        },
        "attachmentMetadata": [],
    }


def _account(db: Session) -> LeaveAccount:
    account = db.scalar(
        select(LeaveAccount).where(
            LeaveAccount.employee_id == "emp_sales_001",
            LeaveAccount.year == 2026,
        )
    )
    assert account is not None
    return account


def test_leave_draft_uses_server_calculated_business_days(
    client: TestClient,
    login: Login,
) -> None:
    login(client, "seojin.yoon@jhworks.test")

    regular = client.post("/api/v1/approvals", json=leave_payload())
    holiday_range = client.post(
        "/api/v1/approvals",
        json=leave_payload("2026-09-23", "2026-09-28"),
    )
    half_day = client.post(
        "/api/v1/approvals",
        json=leave_payload("2026-09-07", "2026-09-07", "HALF_DAY_AM"),
    )

    assert regular.status_code == 201
    assert regular.json()["details"]["requestedDays"] == "3.0"
    assert holiday_range.status_code == 201
    assert holiday_range.json()["details"]["requestedDays"] == "2.0"
    assert half_day.status_code == 201
    assert half_day.json()["details"]["requestedDays"] == "0.5"


def test_submit_reserves_and_approval_confirms_leave(
    client: TestClient,
    login: Login,
    session_factory: sessionmaker[Session],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    draft = client.post("/api/v1/approvals", json=leave_payload()).json()

    submitted = client.post(
        f"/api/v1/approvals/{draft['id']}/submit",
        json={"version": draft["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "PENDING"

    with session_factory() as db:
        account = _account(db)
        event = db.scalar(
            select(WorkCalendarEvent).where(WorkCalendarEvent.approval_id == draft["id"])
        )
        assert account.pending_days == Decimal("3.0")
        assert account.used_days == Decimal("7.0")
        assert event is not None
        assert event.status == AttendanceEventStatus.TENTATIVE

    client.post("/api/v1/auth/logout")
    login(client, "doyun.choi@jhworks.test")
    approved = client.post(
        f"/api/v1/approvals/{draft['id']}/approve",
        json={"version": submitted.json()["version"], "comment": "승인합니다."},
    )
    assert approved.status_code == 200, approved.text

    with session_factory() as db:
        account = _account(db)
        event = db.scalar(
            select(WorkCalendarEvent).where(WorkCalendarEvent.approval_id == draft["id"])
        )
        assert account.pending_days == Decimal("0.0")
        assert account.used_days == Decimal("10.0")
        assert event is not None
        assert event.status == AttendanceEventStatus.CONFIRMED


def test_rejection_releases_leave_and_resubmit_updates_reservation(
    client: TestClient,
    login: Login,
    session_factory: sessionmaker[Session],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    draft = client.post("/api/v1/approvals", json=leave_payload()).json()
    submitted = client.post(
        f"/api/v1/approvals/{draft['id']}/submit",
        json={"version": draft["version"]},
    ).json()

    client.post("/api/v1/auth/logout")
    login(client, "doyun.choi@jhworks.test")
    rejected = client.post(
        f"/api/v1/approvals/{draft['id']}/reject",
        json={"version": submitted["version"], "comment": "날짜를 조정해주세요."},
    )
    assert rejected.status_code == 200

    with session_factory() as db:
        account = _account(db)
        event = db.scalar(
            select(WorkCalendarEvent).where(WorkCalendarEvent.approval_id == draft["id"])
        )
        assert account.pending_days == Decimal("0.0")
        assert event is not None
        assert event.status == AttendanceEventStatus.CANCELED

    client.post("/api/v1/auth/logout")
    login(client, "seojin.yoon@jhworks.test")
    revised = client.post(
        f"/api/v1/approvals/{draft['id']}/revise",
        json={"version": rejected.json()["version"]},
    ).json()
    updated_payload = leave_payload("2026-09-07", "2026-09-07", "HALF_DAY_PM") | {
        "version": revised["version"]
    }
    updated = client.patch(
        f"/api/v1/approvals/{draft['id']}",
        json=updated_payload,
    ).json()
    resubmitted = client.post(
        f"/api/v1/approvals/{draft['id']}/submit",
        json={"version": updated["version"]},
    )
    assert resubmitted.status_code == 200, resubmitted.text

    with session_factory() as db:
        account = _account(db)
        event = db.scalar(
            select(WorkCalendarEvent).where(WorkCalendarEvent.approval_id == draft["id"])
        )
        assert account.pending_days == Decimal("0.5")
        assert event is not None
        assert event.status == AttendanceEventStatus.TENTATIVE
        assert event.start_date == event.end_date


def test_insufficient_balance_does_not_create_reservation(
    client: TestClient,
    login: Login,
    session_factory: sessionmaker[Session],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    draft = client.post(
        "/api/v1/approvals",
        json=leave_payload("2026-10-01", "2026-10-20"),
    ).json()

    response = client.post(
        f"/api/v1/approvals/{draft['id']}/submit",
        json={"version": draft["version"]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_LEAVE_BALANCE"
    with session_factory() as db:
        account = _account(db)
        event = db.scalar(
            select(WorkCalendarEvent).where(WorkCalendarEvent.approval_id == draft["id"])
        )
        assert account.pending_days == Decimal("0.0")
        assert event is None

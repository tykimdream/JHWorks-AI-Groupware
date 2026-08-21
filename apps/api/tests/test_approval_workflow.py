from collections.abc import Callable
from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.models.employee import Employee

Login = Callable[[TestClient, str], None]


def business_trip_payload() -> dict[str, Any]:
    return {
        "type": "BUSINESS_TRIP",
        "title": "Busan client discovery workshop",
        "content": "Meet the client team to define the implementation scope and delivery plan.",
        "amount": 350000,
        "details": {
            "kind": "BUSINESS_TRIP",
            "destination": "Busan",
            "startDate": "2026-09-01",
            "endDate": "2026-09-02",
            "costBreakdown": {
                "transportation": 100000,
                "lodging": 120000,
                "meals": 80000,
                "other": 50000,
            },
            "clientName": "Orbit Retail Lab",
            "visitPurpose": "Define the pilot scope and stakeholder responsibilities.",
        },
        "attachmentMetadata": [],
    }


def create_and_submit(client: TestClient, login: Login) -> dict[str, Any]:
    login(client, "seojin.yoon@jhworks.test")
    created = client.post("/api/v1/approvals", json=business_trip_payload())
    assert created.status_code == 201, created.text
    draft = created.json()

    submitted = client.post(
        f"/api/v1/approvals/{draft['id']}/submit",
        json={"version": draft["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    return cast(dict[str, Any], submitted.json())


def test_draft_submit_and_manager_approve(client: TestClient, login: Login) -> None:
    approval = create_and_submit(client, login)
    assert approval["status"] == "PENDING"
    assert approval["lines"][0]["approver"]["id"] == "emp_sales_mgr_001"

    client.post("/api/v1/auth/logout")
    login(client, "doyun.choi@jhworks.test")
    assigned = client.get("/api/v1/approvals?scope=assigned")
    assert assigned.status_code == 200
    assert assigned.json()["total"] == 1

    approved = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        json={"version": approval["version"], "comment": "Scope and cost are clear."},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["lines"][0]["status"] == "APPROVED"


def test_reject_revise_and_resubmit_preserves_rounds(client: TestClient, login: Login) -> None:
    approval = create_and_submit(client, login)

    client.post("/api/v1/auth/logout")
    login(client, "doyun.choi@jhworks.test")
    rejected = client.post(
        f"/api/v1/approvals/{approval['id']}/reject",
        json={"version": approval["version"], "comment": "Clarify the workshop deliverables."},
    )
    assert rejected.status_code == 200

    client.post("/api/v1/auth/logout")
    login(client, "seojin.yoon@jhworks.test")
    revised = client.post(
        f"/api/v1/approvals/{approval['id']}/revise",
        json={"version": rejected.json()["version"]},
    )
    assert revised.status_code == 200
    assert revised.json()["status"] == "DRAFT"

    resubmitted = client.post(
        f"/api/v1/approvals/{approval['id']}/submit",
        json={"version": revised.json()["version"]},
    )
    assert resubmitted.status_code == 200
    assert [line["round"] for line in resubmitted.json()["lines"]] == [1, 2]
    assert [line["status"] for line in resubmitted.json()["lines"]] == [
        "REJECTED",
        "PENDING",
    ]


def test_non_assigned_manager_cannot_approve(client: TestClient, login: Login) -> None:
    approval = create_and_submit(client, login)

    client.post("/api/v1/auth/logout")
    login(client, "garam.han@jhworks.test")
    response = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        json={"version": approval["version"]},
    )
    assert response.status_code == 403


def test_stale_version_cannot_update_draft(client: TestClient, login: Login) -> None:
    login(client, "seojin.yoon@jhworks.test")
    created = client.post("/api/v1/approvals", json=business_trip_payload()).json()
    update = business_trip_payload() | {"version": created["version"]}
    first_update = client.patch(f"/api/v1/approvals/{created['id']}", json=update)
    assert first_update.status_code == 200

    stale_update = client.patch(f"/api/v1/approvals/{created['id']}", json=update)
    assert stale_update.status_code == 409
    assert stale_update.json()["error"]["code"] == "VERSION_CONFLICT"


def test_incomplete_trip_cannot_be_submitted(client: TestClient, login: Login) -> None:
    login(client, "seojin.yoon@jhworks.test")
    payload = business_trip_payload()
    payload["details"]["visitPurpose"] = None
    draft = client.post("/api/v1/approvals", json=payload).json()

    response = client.post(
        f"/api/v1/approvals/{draft['id']}/submit",
        json={"version": draft["version"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "APPROVAL_NOT_READY"


def test_unrelated_employee_cannot_view_approval(client: TestClient, login: Login) -> None:
    approval = create_and_submit(client, login)

    client.post("/api/v1/auth/logout")
    login(client, "garam.han@jhworks.test")
    response = client.get(f"/api/v1/approvals/{approval['id']}")

    assert response.status_code == 403


def test_rejection_requires_comment(client: TestClient, login: Login) -> None:
    approval = create_and_submit(client, login)

    client.post("/api/v1/auth/logout")
    login(client, "doyun.choi@jhworks.test")
    response = client.post(
        f"/api/v1/approvals/{approval['id']}/reject",
        json={"version": approval["version"], "comment": "  "},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "COMMENT_REQUIRED"


def test_duplicate_decision_is_rejected(client: TestClient, login: Login) -> None:
    approval = create_and_submit(client, login)

    client.post("/api/v1/auth/logout")
    login(client, "doyun.choi@jhworks.test")
    first = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        json={"version": approval["version"]},
    )
    second = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        json={"version": approval["version"]},
    )

    assert first.status_code == 200
    assert second.status_code == 409


def test_submission_requires_active_manager(
    client: TestClient,
    login: Login,
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        employee = db.get(Employee, "emp_sales_001")
        assert employee is not None
        employee.manager_id = None
        db.commit()

    login(client, "seojin.yoon@jhworks.test")
    draft = client.post("/api/v1/approvals", json=business_trip_payload()).json()
    response = client.post(
        f"/api/v1/approvals/{draft['id']}/submit",
        json={"version": draft["version"]},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MANAGER_UNAVAILABLE"


def test_inactive_employee_cannot_login(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        employee = db.get(Employee, "emp_sales_001")
        assert employee is not None
        employee.is_active = False
        db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "seojin.yoon@jhworks.test", "password": "demo1234"},
    )

    assert response.status_code == 401

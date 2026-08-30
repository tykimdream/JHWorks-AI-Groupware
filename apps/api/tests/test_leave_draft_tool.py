from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.approval import Approval
from app.models.attendance import LeaveAccount, WorkCalendarEvent
from app.models.employee import Employee
from app.models.enums import (
    ApprovalStatus,
    AttendanceEventCategory,
    AttendanceEventScope,
    AttendanceEventStatus,
    AttendanceImpact,
    PolicyType,
)
from app.models.policy import CompanyPolicy
from app.services.policy_retrieval import index_active_policy_sections
from tests.conftest import FakePolicyEmbeddingProvider


def _approval_count(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as db:
        return db.scalar(select(func.count()).select_from(Approval)) or 0


def _index_policies(
    session_factory: sessionmaker[Session],
    provider: FakePolicyEmbeddingProvider,
) -> None:
    with session_factory() as db:
        index_active_policy_sections(db, provider, provider.model, provider.dimensions)


def _candidate(client: TestClient) -> dict[str, Any]:
    response = client.get(
        "/api/v1/attendance/leave-availability",
        params={
            "startDate": "2026-09-01",
            "endDate": "2026-09-02",
            "requestedDays": "2.0",
            "limit": 1,
        },
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json()["candidates"][0])


def _prepare(client: TestClient, candidate: dict[str, Any] | None = None):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/leave-draft-tool/prepare",
        json={"candidate": candidate or _candidate(client), "leaveUnit": "FULL_DAY"},
    )


def _confirm(client: TestClient, prepared: dict[str, Any]):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/leave-draft-tool/confirm",
        json={
            "preview": prepared["preview"],
            "confirmationToken": prepared["confirmationToken"],
        },
    )


def test_prepare_returns_exact_preview_without_writing(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    _index_policies(session_factory, fake_embedding_provider)
    before = _approval_count(session_factory)
    login(client, "seojin.yoon@jhworks.test")

    response = _prepare(client)

    assert response.status_code == 200, response.text
    result = response.json()
    preview = result["preview"]
    assert preview["approval"]["type"] == "LEAVE"
    assert preview["approval"]["details"] == {
        "kind": "LEAVE",
        "leaveType": "ANNUAL",
        "leaveUnit": "FULL_DAY",
        "startDate": "2026-09-01",
        "endDate": "2026-09-02",
        "requestedDays": "2.0",
        "reason": None,
        "handoverNote": None,
    }
    assert preview["requestedDays"] == "2.0"
    assert preview["availableDays"] == "9.5"
    assert preview["accountVersion"] == 1
    assert preview["manager"] == {
        "id": "emp_sales_mgr_001",
        "name": "최도윤",
        "position": "Sales Manager",
    }
    assert preview["policyContext"]["status"] == "READY"
    assert all(
        item["policyType"] == "LEAVE" for item in preview["policyContext"]["items"]
    )
    assert result["confirmationToken"]
    assert _approval_count(session_factory) == before


def test_explicit_confirmation_creates_one_editable_draft(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    _index_policies(session_factory, fake_embedding_provider)
    before = _approval_count(session_factory)
    login(client, "seojin.yoon@jhworks.test")
    prepared = _prepare(client).json()

    first = _confirm(client, prepared)
    second = _confirm(client, prepared)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == ApprovalStatus.DRAFT
    assert first.json()["lines"] == []
    assert first.json()["submittedAt"] is None
    assert _approval_count(session_factory) == before + 1


def test_changed_preview_and_candidate_are_rejected(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    _index_policies(session_factory, fake_embedding_provider)
    login(client, "seojin.yoon@jhworks.test")
    prepared = _prepare(client).json()
    prepared["preview"]["approval"]["title"] = "변조한 제목"

    response = _confirm(client, prepared)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LEAVE_PREVIEW_CHANGED"
    assert _approval_count(session_factory) == 0


def test_confirmation_rejects_another_user_and_arbitrary_employee_id(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    _index_policies(session_factory, fake_embedding_provider)
    login(client, "seojin.yoon@jhworks.test")
    candidate = _candidate(client)
    prepared = _prepare(client, candidate).json()

    injected = client.post(
        "/api/v1/leave-draft-tool/prepare",
        json={
            "candidate": candidate,
            "leaveUnit": "FULL_DAY",
            "employeeId": "emp_sales_002",
        },
    )
    assert injected.status_code == 422

    login(client, "doyun.choi@jhworks.test")
    response = _confirm(client, prepared)
    assert response.status_code == 403
    assert _approval_count(session_factory) == 0


def test_account_change_makes_confirmation_stale(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    _index_policies(session_factory, fake_embedding_provider)
    login(client, "seojin.yoon@jhworks.test")
    prepared = _prepare(client).json()
    with session_factory() as db:
        account = db.scalar(
            select(LeaveAccount).where(LeaveAccount.employee_id == "emp_sales_001")
        )
        assert account is not None
        account.pending_days += 1
        account.version += 1
        db.commit()

    response = _confirm(client, prepared)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LEAVE_DRAFT_STALE"
    assert _approval_count(session_factory) == 0


def test_calendar_change_makes_confirmation_stale(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    _index_policies(session_factory, fake_embedding_provider)
    login(client, "seojin.yoon@jhworks.test")
    prepared = _prepare(client).json()
    with session_factory() as db:
        db.add(
            WorkCalendarEvent(
                id="cal_new_blocker",
                category=AttendanceEventCategory.COMPANY_EVENT,
                title="JHWorks 긴급 전사 일정",
                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 1),
                scope=AttendanceEventScope.COMPANY,
                status=AttendanceEventStatus.CONFIRMED,
                impact=AttendanceImpact.BLOCKED,
            )
        )
        db.commit()

    response = _confirm(client, prepared)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LEAVE_DRAFT_STALE"
    assert _approval_count(session_factory) == 0


def test_manager_and_policy_changes_make_confirmation_stale(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    _index_policies(session_factory, fake_embedding_provider)
    login(client, "seojin.yoon@jhworks.test")
    manager_prepared = _prepare(client).json()
    with session_factory() as db:
        actor = db.get(Employee, "emp_sales_001")
        assert actor is not None
        actor.manager_id = "emp_ceo_001"
        db.commit()
    manager_response = _confirm(client, manager_prepared)
    assert manager_response.status_code == 409
    assert manager_response.json()["error"]["code"] == "LEAVE_DRAFT_STALE"

    with session_factory() as db:
        actor = db.get(Employee, "emp_sales_001")
        assert actor is not None
        actor.manager_id = "emp_sales_mgr_001"
        db.commit()
    policy_prepared = _prepare(client).json()
    with session_factory() as db:
        policy = db.scalar(select(CompanyPolicy).where(CompanyPolicy.type == PolicyType.LEAVE))
        assert policy is not None
        policy.content_hash = "f" * 64
        db.commit()
    policy_response = _confirm(client, policy_prepared)
    assert policy_response.status_code == 409
    assert policy_response.json()["error"]["code"] == "LEAVE_DRAFT_STALE"
    assert _approval_count(session_factory) == 0


def test_expired_and_tampered_tokens_are_rejected(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    _index_policies(session_factory, fake_embedding_provider)
    login(client, "seojin.yoon@jhworks.test")
    prepared = _prepare(client).json()

    tampered = prepared.copy()
    tampered["confirmationToken"] = prepared["confirmationToken"] + "x"
    tampered_response = _confirm(client, tampered)
    assert tampered_response.status_code == 409
    assert tampered_response.json()["error"]["code"] == "INVALID_LEAVE_CONFIRMATION"

    settings = get_settings()
    claims = jwt.decode(
        prepared["confirmationToken"],
        options={"verify_signature": False},
    )
    claims["exp"] = datetime.now(UTC) - timedelta(minutes=1)
    expired = prepared.copy()
    expired["confirmationToken"] = jwt.encode(
        claims,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    expired_response = _confirm(client, expired)
    assert expired_response.status_code == 409
    assert expired_response.json()["error"]["code"] == "INVALID_LEAVE_CONFIRMATION"
    assert _approval_count(session_factory) == 0

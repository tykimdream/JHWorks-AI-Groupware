from collections.abc import Callable
from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import ApprovalDraftCandidate, DraftIntent
from app.evals.approval_draft import load_cases
from app.models.approval import Approval
from app.services.policy_retrieval import index_active_policy_sections
from tests.conftest import FakeApprovalDraftProvider, FakePolicyEmbeddingProvider


def complete_trip_candidate() -> ApprovalDraftCandidate:
    return ApprovalDraftCandidate(
        intent=DraftIntent.BUSINESS_TRIP,
        title="부산 고객사 프로젝트 협의 출장",
        content="구현 범위와 다음 단계 담당자를 협의하기 위해 고객사를 방문합니다.",
        amount=350000,
        destination="부산",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 2),
        transportation=100000,
        lodging=120000,
        meals=80000,
        other=50000,
        client_name="하버랩",
        visit_purpose="신규 프로젝트 구현 범위 협의",
    )


def approval_count(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as db:
        return db.scalar(select(func.count()).select_from(Approval)) or 0


def test_prepare_requests_missing_information_without_creating_approval(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    fake_draft_provider.candidate = ApprovalDraftCandidate(
        intent=DraftIntent.BUSINESS_TRIP,
        title="부산 고객사 출장",
        content="고객사 미팅을 위한 출장입니다.",
        destination="부산",
        start_date=date(2026, 9, 1),
    )
    before = approval_count(session_factory)
    login(client, "seojin.yoon@jhworks.test")

    response = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": "다음 주 부산 고객사 출장 결재 작성해줘"},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "NEEDS_INPUT"
    assert result["preview"] is None
    assert result["confirmationToken"] is None
    assert "details.endDate" in result["missingFields"]
    assert "details.costBreakdown" in result["missingFields"]
    assert approval_count(session_factory) == before


def test_follow_up_answers_are_sent_with_a_grounded_date(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    login(client, "seojin.yoon@jhworks.test")

    response = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={
            "request": "다음 주 부산 출장 초안 만들어줘",
            "answers": ["복귀는 수요일이고 총 35만원이야", "하버랩 프로젝트 협의야"],
        },
    )

    assert response.status_code == 200, response.text
    provider_input = fake_draft_provider.inputs[-1]
    assert provider_input.answers == [
        "복귀는 수요일이고 총 35만원이야",
        "하버랩 프로젝트 협의야",
    ]
    assert provider_input.current_date == date.today()
    assert provider_input.timezone == "Asia/Seoul"


def test_preview_requires_explicit_confirmation_and_is_idempotent(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    with session_factory() as db:
        index_active_policy_sections(
            db,
            fake_embedding_provider,
            fake_embedding_provider.model,
            fake_embedding_provider.dimensions,
        )
    fake_draft_provider.candidate = complete_trip_candidate()
    before = approval_count(session_factory)
    login(client, "seojin.yoon@jhworks.test")

    prepared = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": "9월 1일부터 이틀간 부산 하버랩 출장 초안 만들어줘"},
    )

    assert prepared.status_code == 200, prepared.text
    preview_result = prepared.json()
    assert preview_result["status"] == "PREVIEW"
    assert preview_result["policyContext"]["status"] == "READY"
    assert preview_result["confirmationToken"]
    assert approval_count(session_factory) == before

    confirm_payload: dict[str, Any] = {
        "preview": preview_result["preview"],
        "confirmationToken": preview_result["confirmationToken"],
    }
    first = client.post("/api/v1/approval-draft-assistant/confirm", json=confirm_payload)
    second = client.post("/api/v1/approval-draft-assistant/confirm", json=confirm_payload)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "DRAFT"
    assert approval_count(session_factory) == before + 1


def test_confirm_rejects_a_changed_preview(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    fake_draft_provider.candidate = complete_trip_candidate()
    login(client, "seojin.yoon@jhworks.test")
    prepared = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": "부산 출장 초안 만들어줘"},
    ).json()
    prepared["preview"]["amount"] = 1

    response = client.post(
        "/api/v1/approval-draft-assistant/confirm",
        json={
            "preview": prepared["preview"],
            "confirmationToken": prepared["confirmationToken"],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PREVIEW_CHANGED"


def test_confirm_rejects_another_employee(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    fake_draft_provider.candidate = complete_trip_candidate()
    login(client, "seojin.yoon@jhworks.test")
    prepared = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": "부산 출장 초안 만들어줘"},
    ).json()
    login(client, "doyun.choi@jhworks.test")

    response = client.post(
        "/api/v1/approval-draft-assistant/confirm",
        json={
            "preview": prepared["preview"],
            "confirmationToken": prepared["confirmationToken"],
        },
    )

    assert response.status_code == 403


def test_expense_intent_is_not_silently_changed_to_a_trip(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    fake_draft_provider.candidate = ApprovalDraftCandidate(
        intent=DraftIntent.EXPENSE,
        title="CES 출장비 정산",
        content="CES 참석 중 사용한 출장비를 정산합니다.",
        amount=500000,
    )
    before = approval_count(session_factory)
    login(client, "seojin.yoon@jhworks.test")

    response = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": "이번 CES 출장비 사용한 거 전자결재 작성해줘"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "UNSUPPORTED"
    assert "경비 결재" in response.json()["assistantMessage"]
    assert approval_count(session_factory) == before


def test_provider_failure_does_not_create_an_approval(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    fake_draft_provider.should_fail = True
    before = approval_count(session_factory)
    login(client, "seojin.yoon@jhworks.test")

    response = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": "출장 결재 작성해줘"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_DRAFT_UNAVAILABLE"
    assert approval_count(session_factory) == before


def test_approval_draft_eval_dataset_covers_core_intents() -> None:
    cases = load_cases()
    intents = {case.expected_intent for case in cases}

    assert len(cases) >= 5
    assert DraftIntent.BUSINESS_TRIP in intents
    assert DraftIntent.EXPENSE in intents
    assert DraftIntent.LEAVE in intents
    assert DraftIntent.GENERAL in intents

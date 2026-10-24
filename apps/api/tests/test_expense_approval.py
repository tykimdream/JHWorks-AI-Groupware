from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import ApprovalDraftCandidate, DraftIntent
from app.models.enums import ExpenseCategory
from app.services.policy_retrieval import index_active_policy_sections
from tests.conftest import FakeApprovalDraftProvider, FakePolicyEmbeddingProvider

Login = Callable[[TestClient, str], None]


def expense_payload() -> dict[str, Any]:
    return {
        "type": "EXPENSE",
        "title": "CES 출장 경비 정산",
        "content": "CES 협력사 방문을 위해 지출한 교통비를 정산합니다.",
        "amount": 170000,
        "details": {
            "kind": "EXPENSE",
            "expenseDate": (
                datetime.now(ZoneInfo("Asia/Seoul")).date() - timedelta(days=1)
            ).isoformat(),
            "merchant": "코레일",
            "category": "TRANSPORTATION",
            "purpose": "CES 협력사 방문 교통비",
            "receiptReference": "RCP-CES-001",
        },
    }


def test_expense_remains_expense_through_save_edit_submit_and_approve(
    client: TestClient,
    login: Login,
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    payload = expense_payload()
    created = client.post("/api/v1/approvals", json=payload)
    assert created.status_code == 201, created.text
    draft = created.json()
    path = f"/api/v1/approvals/{draft['id']}"
    assert draft["type"] == "EXPENSE"
    assert draft["attachmentMetadata"] == []  # A reference is not an uploaded receipt.
    payload["details"]["merchant"] = "코레일 서울역"
    updated = client.patch(path, json={**payload, "version": draft["version"]})
    assert updated.status_code == 200, updated.text
    submitted = client.post(path + "/submit", json={"version": updated.json()["version"]})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["details"]["merchant"] == "코레일 서울역"
    login(client, "doyun.choi@jhworks.test")
    approved = client.post(path + "/approve", json={"version": submitted.json()["version"]})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["type"] == "EXPENSE"


@pytest.mark.parametrize(
    "field,value",
    [
        ("expenseDate", None),
        ("expenseDate", "2099-01-01"),
        ("merchant", "   "),
        ("category", None),
        ("purpose", ""),
        ("amount", 0),
    ],
)
def test_incomplete_expense_can_be_drafted_but_cannot_be_submitted(
    client: TestClient,
    login: Login,
    field: str,
    value: object,
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    payload = expense_payload()
    if field == "amount":
        payload[field] = value
    else:
        payload["details"][field] = value
    draft = client.post("/api/v1/approvals", json=payload)
    assert draft.status_code == 201, draft.text
    path = f"/api/v1/approvals/{draft.json()['id']}"
    submitted = client.post(path + "/submit", json={"version": draft.json()["version"]})
    assert submitted.status_code == 422, submitted.text
    current = client.get(path).json()
    assert current["status"] == "DRAFT"
    assert current["lines"] == []


def test_expense_preview_is_grounded_signed_and_idempotent(
    client: TestClient,
    login: Login,
    fake_draft_provider: FakeApprovalDraftProvider,
    fake_embedding_provider: FakePolicyEmbeddingProvider,
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        index_active_policy_sections(
            db,
            fake_embedding_provider,
            fake_embedding_provider.model,
            fake_embedding_provider.dimensions,
        )
    fake_draft_provider.candidate = ApprovalDraftCandidate(
        intent=DraftIntent.EXPENSE,
        title="CES 출장 경비 정산",
        content="CES 출장 교통비 정산",
        amount=170000,
        expense_date=datetime.now(ZoneInfo("Asia/Seoul")).date(),
        merchant="코레일",
        expense_category=ExpenseCategory.TRANSPORTATION,
        expense_purpose="CES 출장 교통비",
        receipt_reference="RCP-CES-001",
    )
    login(client, "seojin.yoon@jhworks.test")
    prepared = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": "이번 CES 출장에서 쓴 17만원 정산"},
    ).json()
    assert prepared["status"] == "PREVIEW"
    assert prepared["preview"]["type"] == "EXPENSE"
    assert all(item["policyType"] == "EXPENSE" for item in prepared["policyContext"]["items"])
    assert prepared["policyContext"]["items"]
    assert client.get("/api/v1/approvals?scope=mine").json()["total"] == 0
    confirm = {"preview": prepared["preview"], "confirmationToken": prepared["confirmationToken"]}
    tampered = {
        **prepared["preview"],
        "details": {**prepared["preview"]["details"], "merchant": "변경된 사용처"},
    }
    rejected = client.post(
        "/api/v1/approval-draft-assistant/confirm", json={**confirm, "preview": tampered}
    )
    assert rejected.status_code == 409
    first = client.post("/api/v1/approval-draft-assistant/confirm", json=confirm)
    second = client.post("/api/v1/approval-draft-assistant/confirm", json=confirm)
    assert first.status_code == 201, first.text
    assert second.json()["id"] == first.json()["id"]
    assert client.get("/api/v1/approvals?scope=mine").json()["total"] == 1


def test_receipt_reference_does_not_satisfy_original_receipt_policy(
    client: TestClient,
    login: Login,
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    with session_factory() as db:
        index_active_policy_sections(
            db,
            fake_embedding_provider,
            fake_embedding_provider.model,
            fake_embedding_provider.dimensions,
        )
    login(client, "seojin.yoon@jhworks.test")
    draft = client.post("/api/v1/approvals", json=expense_payload()).json()
    review = client.post(f"/api/v1/approvals/{draft['id']}/ai-review", json={"version": 1})
    assert review.status_code == 200, review.text
    assert "POLICY_RECEIPT_REQUIRED" in {issue["code"] for issue in review.json()["issues"]}

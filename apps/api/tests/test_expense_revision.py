from collections.abc import Callable
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import ApprovalDraftCandidate, DraftIntent
from app.models.approval import Approval
from app.models.enums import ExpenseCategory
from app.models.policy import PolicySection
from tests.conftest import FakeApprovalDraftProvider
from tests.test_expense_approval import expense_payload

Login = Callable[[TestClient, str], None]


def rejected(client: TestClient, login: Login) -> tuple[str, dict[str, Any]]:
    login(client, "seojin.yoon@jhworks.test")
    draft = client.post("/api/v1/approvals", json=expense_payload()).json()
    path = f"/api/v1/approvals/{draft['id']}"
    submitted = client.post(path + "/submit", json={"version": draft["version"]}).json()
    login(client, "doyun.choi@jhworks.test")
    item = client.post(
        path + "/reject",
        json={
            "version": submitted["version"],
            "comment": "업무 목적을 구체적으로 보완하세요. 금액: 999999원",
        },
    ).json()
    login(client, "seojin.yoon@jhworks.test")
    return path, item


def proposal(
    item: dict[str, Any], purpose: str = "CES 협력사 방문 교통비"
) -> ApprovalDraftCandidate:
    from datetime import date

    return ApprovalDraftCandidate(
        intent=DraftIntent.EXPENSE,
        amount=170000,
        expense_date=date.fromisoformat(item["details"]["expenseDate"]),
        merchant="코레일",
        expense_category=ExpenseCategory.TRANSPORTATION,
        expense_purpose=purpose,
        receipt_reference="RCP-CES-001",
    )


def test_revision_is_read_only_and_apply_preserves_history_without_submitting(
    client: TestClient,
    login: Login,
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    path, item = rejected(client, login)
    fake_draft_provider.candidate = proposal(item, "CES 협력사 데모 시연")
    response = client.post(
        path + "/expense-revision/prepare",
        json={
            "version": item["version"],
            "answers": ["목적: CES 협력사 데모 시연"],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["prepared"]["confirmationToken"] is None
    assert result["prepared"]["promptVersion"] == "expense-revision-v1"
    assert any(c["field"] == "details.purpose" for c in result["changes"])
    unchanged = client.get(path).json()
    assert unchanged == item
    apply = {
        "version": item["version"],
        "preview": result["prepared"]["preview"],
        "applyToken": result["applyToken"],
    }
    saved = client.post(path + "/expense-revision/apply", json=apply)
    assert saved.status_code == 200, saved.text
    updated = saved.json()
    assert updated["id"] == item["id"] and updated["status"] == "DRAFT"
    assert updated["version"] == item["version"] + 1 and updated["lines"] == item["lines"]
    assert updated["details"]["purpose"] == "CES 협력사 데모 시연"
    assert client.post(path + "/expense-revision/apply", json=apply).status_code == 409


def test_rejection_amount_is_not_author_evidence(
    client: TestClient,
    login: Login,
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    path, item = rejected(client, login)
    fake_draft_provider.candidate = proposal(item).model_copy(update={"amount": 999999})
    result = client.post(path + "/expense-revision/prepare", json={"version": item["version"]})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["prepared"]["status"] == "NEEDS_INPUT"
    assert body["applyToken"] is None and body["prepared"]["preview"] is None


def test_revision_rechecks_policy_and_binds_document_and_preview(
    client: TestClient,
    login: Login,
    fake_draft_provider: FakeApprovalDraftProvider,
    session_factory: sessionmaker[Session],
) -> None:
    path, item = rejected(client, login)
    fake_draft_provider.candidate = proposal(item)
    result = client.post(
        path + "/expense-revision/prepare", json={"version": item["version"]}
    ).json()
    payload = {
        "version": item["version"],
        "preview": result["prepared"]["preview"],
        "applyToken": result["applyToken"],
    }
    original = payload["preview"]["amount"]
    payload["preview"]["amount"] = 1
    assert client.post(path + "/expense-revision/apply", json=payload).status_code == 409
    payload["preview"]["amount"] = original
    with session_factory() as db:
        section = db.scalar(select(PolicySection).where(PolicySection.section_id == "EXPENSE-2"))
        assert section
        section.content += " changed"
        db.commit()
    assert client.post(path + "/expense-revision/apply", json=payload).status_code == 409
    assert client.get(path).json()["status"] == "REJECTED"


def test_revision_checks_author_version_status_before_provider(
    client: TestClient,
    login: Login,
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    path, item = rejected(client, login)
    with patch.object(fake_draft_provider, "prepare", side_effect=AssertionError("must not call")):
        assert (
            client.post(path + "/expense-revision/prepare", json={"version": 999}).status_code
            == 409
        )
        login(client, "doyun.choi@jhworks.test")
        assert (
            client.post(
                path + "/expense-revision/prepare", json={"version": item["version"]}
            ).status_code
            == 403
        )


def test_decision_brief_is_current_approver_only_and_uses_catalog_without_model(
    client: TestClient,
    login: Login,
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    item = client.post("/api/v1/approvals", json=expense_payload()).json()
    path = f"/api/v1/approvals/{item['id']}"
    item = client.post(path + "/submit", json={"version": item["version"]}).json()
    assert client.get(path + f"/decision-brief?version={item['version']}").status_code == 403
    login(client, "doyun.choi@jhworks.test")
    result = client.get(path + f"/decision-brief?version={item['version']}")
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["version"] == item["version"]
    assert body["policy"]["retrievalChecked"] is False
    assert any(c["outcome"] == "ACTION_REQUIRED" for c in body["policy"]["checks"])
    assert client.get(path + "/decision-brief?version=999").status_code == 409
    assert client.get(path).json() == item


def test_correction_detects_document_change_during_provider_call(
    client: TestClient,
    login: Login,
    fake_draft_provider: FakeApprovalDraftProvider,
    session_factory: sessionmaker[Session],
) -> None:
    path, item = rejected(client, login)
    fake_draft_provider.candidate = proposal(item)
    original = fake_draft_provider.prepare

    def change(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        with session_factory() as db:
            document = db.get(Approval, item["id"])
            assert document
            document.version += 1
            db.commit()
        return result

    with patch.object(fake_draft_provider, "prepare", side_effect=change):
        response = client.post(
            path + "/expense-revision/prepare", json={"version": item["version"]}
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_revision_cannot_mint_new_document_token_or_change_intent(
    client: TestClient,
    login: Login,
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    path, item = rejected(client, login)
    fake_draft_provider.candidate = ApprovalDraftCandidate(
        intent=DraftIntent.GENERAL,
        title="다른 문서",
        content="만들면 안 되는 문서",
    )
    response = client.post(path + "/expense-revision/prepare", json={"version": item["version"]})
    assert response.status_code == 422
    assert client.get(path).json() == item


def test_revision_token_cannot_be_reused_for_another_document(
    client: TestClient,
    login: Login,
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    path, item = rejected(client, login)
    fake_draft_provider.candidate = proposal(item)
    result = client.post(
        path + "/expense-revision/prepare", json={"version": item["version"]}
    ).json()
    other_path, other = rejected(client, login)
    assert other["version"] == item["version"]
    blocked = client.post(
        other_path + "/expense-revision/apply",
        json={
            "version": other["version"],
            "preview": result["prepared"]["preview"],
            "applyToken": result["applyToken"],
        },
    )
    assert blocked.status_code == 409
    assert client.get(other_path).json() == other


def test_public_demo_blocks_new_revision_capability_before_model_call(
    client: TestClient,
    login: Login,
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    from types import SimpleNamespace

    path, item = rejected(client, login)
    with patch(
        "app.services.expense_revision.get_settings",
        return_value=SimpleNamespace(public_demo_enabled=True),
    ), patch.object(
        fake_draft_provider, "prepare", side_effect=AssertionError("must not call")
    ):
        response = client.post(
            path + "/expense-revision/prepare", json={"version": item["version"]}
        )
    assert response.status_code == 403
    assert client.get(path).json() == item

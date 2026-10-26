from collections.abc import Callable
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import PolicyStatus, PolicyType
from app.models.policy import CompanyPolicy, PolicySection
from app.schemas.approval import ApprovalCreate
from app.schemas.policy import PolicyEmbeddingUsage, PolicyRetrievalStatus, PolicySearchResponse
from app.services.expense_policy import validate_expense_policy
from tests.conftest import FakeApprovalDraftProvider, FakePolicyEmbeddingProvider
from tests.test_expense_grounding import TEXT, candidate


def unavailable() -> PolicySearchResponse:
    return PolicySearchResponse(
        status=PolicyRetrievalStatus.UNAVAILABLE,
        items=[],
        provider=None,
        model=None,
        usage=PolicyEmbeddingUsage(input_tokens=0, total_tokens=0),
        latency_ms=0,
    )


def test_catalog_checks_receipt_rule_even_without_paid_retrieval(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    fake_draft_provider.candidate = candidate()
    with patch("app.services.approval_draft._policy_context", return_value=unavailable()):
        result = client.post(
            "/api/v1/approval-draft-assistant/prepare",
            json={"request": TEXT},
        ).json()
    assert result["status"] == "PREVIEW"
    check = result["policyValidation"]
    assert check["status"] == "CATALOG_CHECKED"
    assert check["retrievalChecked"] is False
    receipt = next(c for c in check["checks"] if c["code"] == "RECEIPT_REQUIRED_MIN_TOTAL")
    assert receipt["outcome"] == "ACTION_REQUIRED"  # RCP-001 is not an original receipt.
    assert any(c["outcome"] == "NOT_EVALUATED" for c in check["checks"])
    assert result["confirmationToken"]


def test_changed_policy_blocks_first_save_but_not_successful_replay(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_draft_provider: FakeApprovalDraftProvider,
    session_factory: sessionmaker[Session],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    fake_draft_provider.candidate = candidate()
    first = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": TEXT},
    ).json()
    second = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": TEXT},
    ).json()
    payload = {"preview": first["preview"], "confirmationToken": first["confirmationToken"]}
    saved = client.post("/api/v1/approval-draft-assistant/confirm", json=payload)
    assert saved.status_code == 201
    with session_factory() as db:
        section = db.scalar(select(PolicySection).where(PolicySection.section_id == "EXPENSE-2"))
        assert section
        section.content += " Updated source."
        db.commit()  # Even a text change without updating content_hash invalidates the preview.
    blocked = client.post(
        "/api/v1/approval-draft-assistant/confirm",
        json={
            "preview": second["preview"],
            "confirmationToken": second["confirmationToken"],
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "POLICY_CHANGED"
    replay = client.post("/api/v1/approval-draft-assistant/confirm", json=payload)
    assert replay.status_code == 201 and replay.json()["id"] == saved.json()["id"]


def test_fabricated_retrieval_excerpt_fails_policy_stage_before_signing(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_draft_provider: FakeApprovalDraftProvider,
    session_factory: sessionmaker[Session],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    fake_draft_provider.candidate = candidate()
    preview = ApprovalCreate.model_validate(
        {
            "type": "EXPENSE",
            "title": "검증",
            "content": "검증",
            "amount": 170000,
            "details": {"kind": "EXPENSE"},
            "attachmentMetadata": [],
        }
    )
    with session_factory() as db:
        source = validate_expense_policy(db, preview, unavailable()).citations[0]
    forged = source.model_copy(update={"excerpt": "영수증이 필요 없다는 발명된 규정"})
    retrieved = unavailable().model_copy(
        update={"status": PolicyRetrievalStatus.READY, "items": [forged]}
    )
    with patch("app.services.approval_draft._policy_context", return_value=retrieved):
        response = client.post(
            "/api/v1/approval-draft-assistant/prepare",
            json={"request": TEXT},
        )
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "AI_POLICY_EVIDENCE_INVALID"
    assert error["details"]["execution"]["stages"][-1]["stage"] == "policy"
    assert "발명된" not in response.text


def test_inactive_policy_is_not_used_as_a_rule_source(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_draft_provider: FakeApprovalDraftProvider,
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    del fake_embedding_provider
    with session_factory() as db:
        for policy in db.scalars(
            select(CompanyPolicy).where(CompanyPolicy.type == PolicyType.EXPENSE)
        ):
            policy.status = PolicyStatus.ARCHIVED
        db.commit()
    login(client, "seojin.yoon@jhworks.test")
    fake_draft_provider.candidate = candidate()
    response = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": TEXT},
    )
    assert response.status_code == 200, response.text
    check = response.json()["policyValidation"]
    assert check["status"] == "UNAVAILABLE" and check["checks"] == []

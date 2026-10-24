from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.models.approval import Approval
from app.models.enums import ApprovalStatus
from tests.test_demo_workspace import set_actor, setup_workspaces
from tests.test_expense_approval import expense_payload

Login = Callable[[TestClient, str], None]


def create(client: TestClient, **details: object) -> dict[str, Any]:
    payload = expense_payload()
    payload["details"].update(details)
    response = client.post("/api/v1/approvals", json=payload)
    assert response.status_code == 201, response.text
    return dict(response.json())


def test_exact_duplicate_evidence_is_read_only_and_rejected_documents_are_excluded(
    client: TestClient,
    login: Login,
    session_factory: sessionmaker[Session],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    first, second = create(client), create(client)
    path = f"/api/v1/approvals/{first['id']}/expense-checks"
    result = client.get(path)
    assert result.status_code == 200, result.text
    assert [item["id"] for item in result.json()["duplicateMatches"]] == [second["id"]]
    assert result.json()["version"] == first["version"]
    current = client.get(f"/api/v1/approvals/{first['id']}").json()
    assert current["version"] == first["version"] and current["status"] == "DRAFT"
    with session_factory() as db:
        approval = db.get(Approval, second["id"])
        assert approval is not None
        approval.status = ApprovalStatus.REJECTED
        db.commit()
    assert client.get(path).json()["duplicateMatches"] == []


def test_manager_never_receives_an_unassigned_draft_as_evidence(
    client: TestClient,
    login: Login,
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    first, hidden = create(client), create(client)
    submitted = client.post(f"/api/v1/approvals/{first['id']}/submit", json={"version": 1})
    assert submitted.status_code == 200
    login(client, "doyun.choi@jhworks.test")
    result = client.get(f"/api/v1/approvals/{first['id']}/expense-checks")
    assert result.status_code == 200
    assert result.json()["duplicateMatches"] == []
    assert client.get(f"/api/v1/approvals/{hidden['id']}/expense-checks").status_code == 403
    assert client.get("/api/v1/approvals/expense-insights").json()["items"] == []


def test_another_author_with_same_payment_facts_is_not_a_duplicate(
    client: TestClient,
    login: Login,
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    first = create(client)
    login(client, "doyun.choi@jhworks.test")
    other = create(client)
    assert (
        client.get(f"/api/v1/approvals/{other['id']}/expense-checks").json()["duplicateMatches"]
        == []
    )
    assert client.get(f"/api/v1/approvals/{first['id']}/expense-checks").status_code == 403


def test_missing_purpose_still_allows_comparing_known_payment_facts(
    client: TestClient,
    login: Login,
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    first = create(client, purpose="")
    second = create(client)
    result = client.get(f"/api/v1/approvals/{first['id']}/expense-checks").json()
    assert result["missingFields"] == ["details.purpose"]
    assert result["duplicateMatches"][0]["id"] == second["id"]


def test_home_and_evidence_are_bounded_and_do_not_claim_complete_coverage(
    client: TestClient,
    login: Login,
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    first = create(client)
    for _ in range(11):
        create(client)
    result = client.get("/api/v1/approvals/expense-insights").json()
    assert result["checkedCount"] == 10 and result["hasMoreDocuments"] is True
    assert len(result["items"]) == 10
    evidence = client.get(f"/api/v1/approvals/{first['id']}/expense-checks").json()
    assert len(evidence["duplicateMatches"]) == 3 and evidence["moreMatches"] is True


def test_cross_workspace_source_and_evidence_are_hidden(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    setup_workspaces(session_factory)
    set_actor(client, "emp_sales_001")
    source = create(client)
    set_actor(client, "emp_eng_001")
    create(client)
    assert client.get(f"/api/v1/approvals/{source['id']}/expense-checks").status_code == 403
    assert client.get("/api/v1/approvals/expense-insights").json()["items"] == []


@pytest.mark.parametrize("changed", [{"merchant": "다른 사용처"}, {"expenseDate": "2026-01-01"}])
def test_different_payment_facts_are_not_a_duplicate(
    client: TestClient,
    login: Login,
    changed: dict[str, object],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    source = create(client)
    create(client, **changed)
    assert (
        client.get(f"/api/v1/approvals/{source['id']}/expense-checks").json()["duplicateMatches"]
        == []
    )

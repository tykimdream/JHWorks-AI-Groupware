from collections.abc import Callable
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.approval import Approval, ApprovalLine
from app.models.employee import Employee
from app.models.enums import ApprovalLineStatus


def test_summary_page_limits_sorts_and_respects_scope(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    ids = []
    for index in range(3):
        response = client.post("/api/v1/approvals", json={
            "type": "GENERAL", "title": f"문서 {index}", "content": "x" * 300,
            "details": {"kind": "GENERAL"},
        })
        assert response.status_code == 201
        ids.append(response.json()["id"])
    with session_factory() as db:
        for item in db.scalars(select(Approval).where(Approval.id.in_(ids))):
            item.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
        db.commit()
    response = client.get("/api/v1/approvals/summaries", params={"limit": 2, "status": "DRAFT"})
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 3
    assert [item["id"] for item in page["items"]] == sorted(ids, reverse=True)[:2]
    assert len(page["items"][0]["contentPreview"]) == 200
    assert "lines" not in page["items"][0]
    assert "attachmentMetadata" not in page["items"][0]
    second = client.get("/api/v1/approvals/summaries", params={"limit": 2, "offset": 2})
    assert [item["id"] for item in second.json()["items"]] == sorted(ids, reverse=True)[2:]
    assert client.get("/api/v1/approvals/summaries", params={"limit": 51}).status_code == 422
    login(client, "doyun.choi@jhworks.test")
    assert client.get("/api/v1/approvals/summaries").json()["total"] == 0
    assigned = client.get("/api/v1/approvals/summaries", params={"scope": "assigned"})
    assert assigned.json()["total"] == 0


def test_assigned_pending_only_includes_current_pending_approver(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    draft = client.post("/api/v1/approvals", json={
        "type": "GENERAL", "title": "검토할 문서", "content": "합성 자료",
        "details": {"kind": "GENERAL"},
    }).json()
    submitted = client.post(f"/api/v1/approvals/{draft['id']}/submit", json={
        "version": draft["version"],
    })
    assert submitted.status_code == 200
    login(client, "doyun.choi@jhworks.test")
    params = {"scope": "assigned", "status": "PENDING"}
    assert client.get("/api/v1/approvals/summaries", params=params).json()["total"] == 1
    assert client.get("/api/v1/approvals/home-summary").json()["pendingAssigned"] == 1
    # The actor participated in an earlier round, but another approver is pending now.
    with session_factory() as db:
        line = db.scalar(select(ApprovalLine).where(ApprovalLine.approval_id == draft["id"]))
        other = db.scalar(select(Employee).where(Employee.email == "garam.han@jhworks.test"))
        assert line is not None and other is not None
        line.status = ApprovalLineStatus.REJECTED
        db.add(ApprovalLine(id="synthetic-next-line", approval_id=draft["id"], step=1,
                            round=2, approver_id=other.id, status=ApprovalLineStatus.PENDING))
        db.commit()
    assert client.get("/api/v1/approvals/summaries", params=params).json()["total"] == 0
    assert client.get("/api/v1/approvals/home-summary").json()["pendingAssigned"] == 0
    assigned = client.get("/api/v1/approvals/summaries", params={"scope": "assigned"})
    assert assigned.json()["total"] == 1


def test_home_summary_counts_all_documents_and_returns_bounded_recent(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    for index in range(23):
        response = client.post("/api/v1/approvals", json={
            "type": "GENERAL", "title": f"홈 문서 {index}", "content": "합성 자료",
            "details": {"kind": "GENERAL"},
        })
        assert response.status_code == 201
    result = client.get("/api/v1/approvals/home-summary")
    assert result.status_code == 200
    home = result.json()
    assert home["mineTotal"] == 23
    assert home["mineDraft"] == 23
    assert len(home["recent"]) == 4
    assert home["nextDocument"]["status"] == "DRAFT"
    assert "lines" not in home["recent"][0]
    login(client, "doyun.choi@jhworks.test")
    other = client.get("/api/v1/approvals/home-summary").json()
    assert other["mineTotal"] == 0
    assert other["recent"] == []
    assert other["nextDocument"] is None

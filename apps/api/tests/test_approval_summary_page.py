from collections.abc import Callable
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.approval import Approval


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

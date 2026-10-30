"""PostgreSQL-only approval list regression; never connects to staging or remote DBs."""

import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.database import Base
from app.ops.staging_fixture import populate

PASSWORD = "synthetic-postgres-regression-password"


@pytest.fixture
def session_factory() -> Generator[sessionmaker[Session], None, None]:
    raw = os.environ.get("JHWORKS_TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("dedicated local PostgreSQL test URL not configured")
    url = make_url(raw)
    if (url.drivername != "postgresql+psycopg"
            or url.host not in {"localhost", "127.0.0.1", "::1"}
            or url.database != "jhworks_test" or url.username != "jhworks_test"):
        pytest.fail("only the dedicated loopback jhworks_test database/user is allowed")
    schema = "approval_test_" + uuid4().hex
    engine = create_engine(url, execution_options={"schema_translate_map": {None: schema}})
    created = False
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(CreateSchema(schema))
            created = True
            Base.metadata.create_all(connection)
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as db, db.begin():
            populate(db, PASSWORD, 2026)
        yield factory
    finally:
        try:
            if created:
                with engine.begin() as connection:
                    connection.execute(DropSchema(schema, cascade=True))
        finally:
            engine.dispose()


def login_actor(client: TestClient, actor: str) -> None:
    response = client.post("/api/v1/auth/login",
                           json={"email": f"staging.{actor}@jhworks.test", "password": PASSWORD})
    assert response.status_code == 200


@pytest.mark.parametrize("actor", ["author", "approver", "unrelated"])
@pytest.mark.parametrize("scope", ["mine", "assigned"])
def test_empty_postgres_list(client: TestClient, actor: str, scope: str) -> None:
    login_actor(client, actor)
    response = client.get("/api/v1/approvals", params={"scope": scope})
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_postgres_multiple_rounds_preserve_json_without_duplicate_or_leaked_items(
    client: TestClient,
) -> None:
    login_actor(client, "author")
    created = client.post("/api/v1/approvals", json={
        "type": "GENERAL", "title": "Synthetic PostgreSQL regression",
        "content": "Synthetic independent approval data.",
        "details": {"kind": "GENERAL"},
        "attachmentMetadata": [{"name": "synthetic.txt", "contentType": "text/plain"}],
    })
    assert created.status_code == 201
    draft = created.json()
    path = "/api/v1/approvals/" + draft["id"]
    submitted = client.post(path + "/submit", json={"version": draft["version"]})
    assert submitted.status_code == 200

    client.post("/api/v1/auth/logout")
    login_actor(client, "approver")
    rejected = client.post(path + "/reject", json={
        "version": submitted.json()["version"], "comment": "Synthetic revision requested",
    })
    assert rejected.status_code == 200
    client.post("/api/v1/auth/logout")
    login_actor(client, "author")
    revised = client.post(path + "/revise", json={"version": rejected.json()["version"]})
    assert revised.status_code == 200
    resubmitted = client.post(path + "/submit", json={"version": revised.json()["version"]})
    assert resubmitted.status_code == 200

    client.post("/api/v1/auth/logout")
    login_actor(client, "approver")
    assigned = client.get("/api/v1/approvals", params={"scope": "assigned"})
    assert assigned.status_code == 200
    result = assigned.json()
    assert result["total"] == 1
    assert [item["id"] for item in result["items"]] == [draft["id"]]
    summary = client.get("/api/v1/approvals/summaries", params={"scope": "assigned", "limit": 1})
    assert summary.status_code == 200
    assert summary.json()["total"] == 1
    assert summary.json()["items"][0]["id"] == draft["id"]
    assert summary.json()["items"][0]["lineCount"] == 2
    item = result["items"][0]
    assert item["details"] == {"kind": "GENERAL"}
    assert item["attachmentMetadata"] == [{"name": "synthetic.txt", "contentType": "text/plain"}]
    assert [line["round"] for line in item["lines"]] == [1, 2]

    client.post("/api/v1/auth/logout")
    login_actor(client, "unrelated")
    hidden = client.get("/api/v1/approvals", params={"scope": "assigned"})
    assert hidden.status_code == 200
    assert hidden.json() == {"items": [], "total": 0}
    hidden_summary = client.get("/api/v1/approvals/summaries", params={"scope": "assigned"})
    assert hidden_summary.status_code == 200
    assert hidden_summary.json()["total"] == 0
    assert client.get(path).status_code == 403


def test_synthetic_service_baseline_reports_visible_rows_and_serialization() -> None:
    from app.ops.approval_list_benchmark import run

    raw = os.environ.get("JHWORKS_TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("dedicated local PostgreSQL test URL not configured")
    report = run(raw, [4], 2)
    assert report["fixtureVersion"] == "approval-list-v1"
    assert "synthetic-ci-only" not in str(report)
    cases = {case["actor"]: case for case in report["cases"]}
    for actor, expected in (("author", 3), ("approver", 4), ("outsider", 0)):
        samples = cases[actor]["samples"]
        assert len(samples) == 2
        assert all(sample["rows"] == expected for sample in samples)
        assert all(sample["sqlStatements"] >= 1 for sample in samples)
        assert all(sample["payloadBytes"] > 0 for sample in samples)
        assert cases[actor]["medianTotalMs"] >= 0

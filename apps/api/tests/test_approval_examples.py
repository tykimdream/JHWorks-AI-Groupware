from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import ApprovalDraftCandidate, DraftIntent
from app.models.approval_example import ApprovalExample
from app.services.approval_example_corpus import EXAMPLES
from app.services.approval_examples import index_examples, search_examples
from tests.conftest import FakeApprovalDraftProvider, FakePolicyEmbeddingProvider


def test_example_index_is_idempotent_and_excludes_unknown_documents(
    session_factory: sessionmaker[Session], fake_embedding_provider: FakePolicyEmbeddingProvider
) -> None:
    with session_factory() as db:
        provider = fake_embedding_provider
        assert index_examples(db, provider, provider.model, provider.dimensions) == len(EXAMPLES)
        assert index_examples(db, provider, provider.model, provider.dimensions) == 0
        db.add(
            ApprovalExample(
                id="private",
                title="private",
                content="secret",
                outline=["secret"],
                embedding=[1.0] * provider.dimensions,
                embedding_model=provider.model,
                content_hash="wrong",
            )
        )
        db.commit()
        status, matches = search_examples(
            db, provider, "인터뷰 결과 보고", provider.model, provider.dimensions
        )
        assert status == "READY"
        assert matches and all(row.id != "private" for row in matches)
        matches[0].outline = ["tampered"]
        db.commit()
        _, after = search_examples(
            db, provider, "인터뷰 결과 보고", provider.model, provider.dimensions
        )
        assert all(row.outline != ["tampered"] for row in after)


def test_general_draft_uses_example_bodies_and_suggests_current_manager(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    with session_factory() as db:
        index_examples(
            db,
            fake_embedding_provider,
            fake_embedding_provider.model,
            fake_embedding_provider.dimensions,
        )
    fake_draft_provider.candidate = ApprovalDraftCandidate(
        intent=DraftIntent.GENERAL, title="인터뷰 결과", content="업무 인터뷰를 정리합니다."
    )
    login(client, "seojin.yoon@jhworks.test")
    response = client.post(
        "/api/v1/approval-draft-assistant/prepare", json={"request": "인터뷰 결과 보고 작성"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["exampleStatus"] == "READY"
    assert data["examples"]
    provider_input = fake_draft_provider.inputs[-1]
    assert [item.content for item in provider_input.example_references] == [
        item["content"] for item in data["examples"]
    ]
    assert all("[" in item.content for item in provider_input.example_references)
    assert data["approverSuggestion"] is not None
    assert data["preview"] and data["confirmationToken"]


def test_unavailable_embedding_falls_back_without_examples(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    with session_factory() as db:
        index_examples(
            db,
            fake_embedding_provider,
            fake_embedding_provider.model,
            fake_embedding_provider.dimensions,
        )
    fake_embedding_provider.should_fail = True
    login(client, "seojin.yoon@jhworks.test")
    response = client.post(
        "/api/v1/approval-draft-assistant/prepare", json={"request": "인터뷰 결과 보고 작성"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["exampleStatus"] == "UNAVAILABLE"
    assert not fake_draft_provider.inputs[-1].example_references


def test_corpus_has_distinct_detailed_placeholder_documents() -> None:
    ids = [key for key, _, _, _ in EXAMPLES]
    assert len(ids) >= 20
    assert len(ids) == len(set(ids))
    for _, title, body, outline in EXAMPLES:
        assert title and len(outline) >= 3
        assert all(heading in body for heading in outline)
        assert "[" in body and "]" in body
        assert len(body) > 100

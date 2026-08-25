from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.evals.policy_retrieval import load_cases
from app.services.policy_retrieval import index_active_policy_sections
from tests.conftest import FakePolicyEmbeddingProvider


def test_active_policies_have_stable_sections(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "garam.han@jhworks.test")
    response = client.get("/api/v1/policies")

    assert response.status_code == 200
    policies = response.json()
    assert {policy["id"] for policy in policies} == {
        "policy_travel",
        "policy_expense",
        "policy_leave",
    }
    assert all(policy["version"] == "1.0" for policy in policies)
    assert all(policy["sections"] for policy in policies)


def test_policy_indexing_is_incremental(
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    with session_factory() as db:
        first = index_active_policy_sections(
            db,
            fake_embedding_provider,
            fake_embedding_provider.model,
            fake_embedding_provider.dimensions,
        )
        second = index_active_policy_sections(
            db,
            fake_embedding_provider,
            fake_embedding_provider.model,
            fake_embedding_provider.dimensions,
        )

    assert first[:2] == (10, 0)
    assert second[:2] == (0, 10)


def test_policy_search_returns_stable_section_citation(
    client: TestClient,
    login: Callable[[TestClient, str], None],
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

    response = client.post(
        "/api/v1/policies/search",
        json={"query": "국내 출장 숙박비 한도", "policyType": "TRAVEL", "topK": 4},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "READY"
    assert result["items"][0]["citationKey"] == "policy_travel:1.0:TRAVEL-1"
    assert result["items"][0]["sectionId"] == "TRAVEL-1"
    assert result["items"][0]["excerpt"]
    assert result["provider"] == "fake"


def test_policy_search_reports_unindexed_knowledge_base(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "seojin.yoon@jhworks.test")

    response = client.post(
        "/api/v1/policies/search",
        json={"query": "출장 숙박비", "policyType": "TRAVEL"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "NOT_INDEXED"
    assert response.json()["items"] == []


def test_policy_search_reports_provider_failure_without_losing_index(
    client: TestClient,
    login: Callable[[TestClient, str], None],
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
    fake_embedding_provider.should_fail = True
    login(client, "seojin.yoon@jhworks.test")

    response = client.post(
        "/api/v1/policies/search",
        json={"query": "출장 숙박비", "policyType": "TRAVEL"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "UNAVAILABLE"
    assert response.json()["items"] == []


def test_policy_retrieval_eval_dataset_covers_each_policy_domain() -> None:
    cases = load_cases()
    case_ids = {case.id for case in cases}

    assert len(cases) >= 6
    assert "travel-accommodation-limit" in case_ids
    assert "expense-receipt-threshold" in case_ids
    assert "leave-advance-notice" in case_ids

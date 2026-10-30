from collections.abc import Callable
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import ApprovalDraftCandidate, ApprovalDraftProviderInput, DraftIntent
from app.services.approval_examples import index_examples
from app.services.grounded_general_draft import structured_general_draft
from tests.conftest import FakeApprovalDraftProvider, FakePolicyEmbeddingProvider

EXAMPLE = ("가상 인터뷰 보고", ["개요", "업무 내용", "업무 기간", "주요 산출물", "참여 인원"])


def _input(request: str, answers: list[str] | None = None) -> ApprovalDraftProviderInput:
    return ApprovalDraftProviderInput(
        request=request,
        answers=answers or [],
        current_date=date(2026, 10, 30),
        timezone="Asia/Seoul",
    )


def test_structured_draft_preserves_original_facts_and_rejects_model_claims() -> None:
    original = _input(
        "문서 유형: 일반\n제목: 가상 인터뷰 보고\n개요: 새로운 서비스의 인터뷰를 진행했습니다.\n"
        "업무 내용: 접근 권한을 논의했습니다.\n업무 기간: 2026-03-10\n"
        "참여 인원: 가상인물123과 가상인물456"
    )
    candidate = ApprovalDraftCandidate(
        intent=DraftIntent.EXPENSE,
        title="가짜 제목",
        content="승인받았으며 예산은 500만원입니다.",
        amount=5000000,
    )
    result = structured_general_draft(candidate, original, [EXAMPLE])
    assert result is not None
    assert result.candidate.intent == DraftIntent.GENERAL
    assert result.candidate.amount is None
    assert result.candidate.title == "가상 인터뷰 보고"
    assert result.example_title == EXAMPLE[0]
    assert result.missing_fields == ["주요 산출물"]
    assert result.candidate.content is not None
    assert "500만원" not in result.candidate.content and "승인받았" not in result.candidate.content
    assert "1. 개요\n새로운 서비스의 인터뷰를 진행했습니다." in result.candidate.content
    for fact in result.facts:
        assert original.request[fact.start : fact.end] == fact.value
        assert fact.value in (result.candidate.title, result.candidate.content) or (
            fact.field != "제목" and fact.value in result.candidate.content
        )


def test_ambiguous_corrections_or_unlabelled_input_do_not_get_rewritten() -> None:
    candidate = ApprovalDraftCandidate(intent=DraftIntent.GENERAL, title="제목", content="본문")
    for source in (
        _input("제목: 보고\n업무 내용: 첫 내용", ["업무 내용: 정정한 내용"]),
        _input("제목: 보고\n업무 내용: 내용\n승인하지 않았습니다."),
        _input("문서 유형: 출장\n제목: 보고\n개요: 내용\n업무 내용: 작업"),
    ):
        assert structured_general_draft(candidate, source, [EXAMPLE]) is None


def test_api_traces_facts_without_sending_them_to_external_providers(
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
    fake_embedding_provider.texts.clear()
    fake_draft_provider.candidate = ApprovalDraftCandidate(
        intent=DraftIntent.GENERAL, title="근거 없는 제목", content="비용 500만원이 승인됐습니다."
    )
    request = (
        "문서 유형: 일반\n제목: 인터뷰 업무 보고\n개요: 가상인물123과 인터뷰했습니다.\n"
        "업무 내용: 기능 범위를 논의했습니다.\n참여 인원: 가상인물123"
    )
    login(client, "seojin.yoon@jhworks.test")
    response = client.post("/api/v1/approval-draft-assistant/prepare", json={"request": request})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["generalVerification"] == "STRUCTURED_INPUT_MATCHED"
    assert data["preview"]["title"] == "인터뷰 업무 보고"
    assert "500만원" not in data["preview"]["content"]
    for fact in data["generalEvidence"]:
        assert request[fact["start"] : fact["end"]] == fact["text"]
    outbound = fake_draft_provider.inputs[-1].model_dump_json()
    assert "가상인물123" not in outbound
    assert all("가상인물123" not in text for text in fake_embedding_provider.texts)


def test_local_retrieval_keeps_raw_text_on_loopback_and_uses_masked_model_input(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    from unittest.mock import patch

    from app.core.config import get_settings
    from app.services import local_example_search

    with session_factory() as db:
        index_examples(
            db,
            fake_embedding_provider,
            fake_embedding_provider.model,
            fake_embedding_provider.dimensions,
        )
    fake_embedding_provider.texts.clear()
    fake_draft_provider.candidate = ApprovalDraftCandidate(
        intent=DraftIntent.GENERAL, title="가짜", content="입력하지 않은 사실"
    )
    captured: list[str] = []

    def local_embedding(texts: list[str]) -> list[list[float]]:
        captured.extend(texts)
        return [[1.0] + [0.0] * 1023 for _ in texts]

    request = (
        "문서 유형: 일반\n제목: 인터뷰 보고\n개요: 가상인물123과 논의했습니다.\n"
        "업무 내용: 권한을 확인했습니다."
    )
    login(client, "seojin.yoon@jhworks.test")
    with (
        patch.object(get_settings(), "local_example_search_enabled", True),
        patch.object(local_example_search, "_cache_vectors", None),
        patch.object(local_example_search, "_cache_key", None),
        patch.object(local_example_search, "_embed", side_effect=local_embedding),
    ):
        response = client.post(
            "/api/v1/approval-draft-assistant/prepare", json={"request": request}
        )
    assert response.status_code == 200, response.text
    assert response.json()["exampleRetrieval"] == "LOCAL"
    assert request in captured
    assert "가상인물123" not in fake_draft_provider.inputs[-1].model_dump_json()
    assert all("가상인물123" not in text for text in fake_embedding_provider.texts)


def test_local_search_failure_uses_only_safe_topic_for_remote_embedding(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    from unittest.mock import patch

    from app.core.config import get_settings
    from app.services.local_example_search import LocalSearchUnavailable

    with session_factory() as db:
        index_examples(
            db,
            fake_embedding_provider,
            fake_embedding_provider.model,
            fake_embedding_provider.dimensions,
        )
    fake_embedding_provider.texts.clear()
    login(client, "seojin.yoon@jhworks.test")
    with (
        patch.object(get_settings(), "local_example_search_enabled", True),
        patch(
            "app.services.approval_draft.search_local_examples", side_effect=LocalSearchUnavailable
        ),
    ):
        response = client.post(
            "/api/v1/approval-draft-assistant/prepare",
            json={
                "request": "인터뷰 가상인물123과 관련된 업무 요청",
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["exampleRetrieval"] == "SAFE_TOPICS_AFTER_LOCAL_FAILURE"
    assert fake_embedding_provider.texts
    assert all("가상인물123" not in text for text in fake_embedding_provider.texts)

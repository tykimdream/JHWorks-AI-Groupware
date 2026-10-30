from collections.abc import Callable
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import ApprovalDraftCandidate, ApprovalDraftProviderInput, DraftIntent
from app.services.approval_examples import index_examples
from app.services.natural_general_draft import natural_general_draft
from tests.conftest import FakeApprovalDraftProvider, FakePolicyEmbeddingProvider


def original(request: str, answers: list[str] | None = None) -> ApprovalDraftProviderInput:
    return ApprovalDraftProviderInput(
        request=request,
        answers=answers or [],
        current_date=date(2026, 10, 30),
        timezone="Asia/Seoul",
    )


def test_unlabelled_input_keeps_every_fact_and_rejects_invented_text() -> None:
    request = (
        "가상서비스 기획을 위해 가상인물123과 인터뷰했어. 기능 범위와 권한을 논의했어. "
        "기간은 2026. 03. 10. 참여자는 가상인물123과 가상인물456이야."
    )
    value = original(request)
    candidate = ApprovalDraftCandidate(
        intent=DraftIntent.GENERAL,
        title="가짜 승인",
        content="500만원 예산을 승인받았습니다.",
        amount=5000000,
    )
    result = natural_general_draft(
        candidate, value, [("가상 인터뷰 결과", ["개요", "업무 내용", "업무 기간", "참여 인원"])]
    )
    assert result is not None and result.example_title == "가상 인터뷰 결과"
    assert result.candidate.content is not None
    assert "500만원" not in result.candidate.content and "승인받" not in result.candidate.content
    assert "인터뷰했습니다." in result.candidate.content
    assert "권한을 논의했습니다." in result.candidate.content
    assert "2026. 03. 10." in result.candidate.content
    assert "참여자는 가상인물123과 가상인물456입니다." in result.candidate.content
    assert result.candidate.amount is None
    assert [fact.text for fact in result.facts] == [
        "가상서비스 기획을 위해 가상인물123과 인터뷰했어.",
        "기능 범위와 권한을 논의했어.",
        "기간은 2026. 03. 10.",
        "참여자는 가상인물123과 가상인물456이야.",
    ]
    for fact in result.facts:
        assert request[fact.start : fact.end] == fact.text
        assert fact.draft_text in result.candidate.content


def test_negation_is_preserved_and_corrections_are_not_interpreted() -> None:
    candidate = ApprovalDraftCandidate(intent=DraftIntent.GENERAL)
    result = natural_general_draft(candidate, original("그 비용을 승인하지 않았어."), [])
    assert result is not None and result.candidate.content is not None
    assert "승인하지 않았어" in result.candidate.content
    negative = natural_general_draft(candidate, original("그건 승인이 아니야."), [])
    assert negative is not None and negative.candidate.content is not None
    assert "승인이 아니야." in negative.candidate.content
    corrected = original("인터뷰를 3월에 진행했어.", ["아니, 4월로 정정할게."])
    assert natural_general_draft(candidate, corrected, []) is None
    competing = original("기간은 3월이야.", ["기간은 4월이야."])
    assert natural_general_draft(candidate, competing, []) is None


def test_natural_api_exposes_sources_but_masks_provider_inputs(
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
        intent=DraftIntent.GENERAL, title="가짜", content="승인 및 비용 500만원"
    )
    request = "가상인물123과 인터뷰했어. 기능 범위를 논의했어. 참여자는 가상인물123이야."
    login(client, "seojin.yoon@jhworks.test")
    response = client.post("/api/v1/approval-draft-assistant/prepare", json={"request": request})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["generalVerification"] == "NATURAL_INPUT_MATCHED"
    assert "인터뷰했습니다." in data["preview"]["content"]
    assert "500만원" not in data["preview"]["content"]
    for fact in data["generalEvidence"]:
        assert request[fact["start"] : fact["end"]] == fact["text"]
        assert fact["draftText"] in data["preview"]["content"]
    assert "가상인물123" not in fake_draft_provider.inputs[-1].model_dump_json()
    assert all("가상인물123" not in text for text in fake_embedding_provider.texts)

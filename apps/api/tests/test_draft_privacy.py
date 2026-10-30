from collections.abc import Callable
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import ApprovalDraftCandidate, ApprovalDraftProviderInput, DraftIntent
from app.services.approval_examples import index_examples
from app.services.draft_privacy import mask_draft_input, restore_text
from app.services.general_draft_verification import verify_general_draft
from tests.conftest import FakeApprovalDraftProvider, FakePolicyEmbeddingProvider


def test_all_user_tokens_are_masked_and_local_map_is_not_serialized() -> None:
    value = ApprovalDraftProviderInput(
        request="인터뷰 담당자: 가상인물123 연락처 010-0000-0000 메일 test@example.invalid",
        answers=["가상인물123 참석"],
        current_date=date(2026, 10, 30),
        timezone="Asia/Seoul",
        revision_context="반려 의견: 비밀정보456",
    )
    masked = mask_draft_input(value)
    wire = masked.value.model_dump_json()
    for secret in ("가상인물123", "010-0000-0000", "test@example.invalid", "비밀정보456"):
        assert secret not in wire
    assert restore_text(masked.value.request, masked.value.private_token_map) == value.request
    assert restore_text(masked.value.answers[0], masked.value.private_token_map) == value.answers[0]
    assert masked.topic_query == "인터뷰 결과 보고"


def test_explicit_fields_restore_without_exposing_values() -> None:
    value = ApprovalDraftProviderInput(
        request="경비 정산; 금액: 38000원; 사용처: 가상상점; 분류: 교통비",
        answers=[],
        current_date=date(2026, 10, 30),
        timezone="Asia/Seoul",
    )
    masked = mask_draft_input(value).value
    assert restore_text(masked.field_hints["amount"], masked.private_token_map) == "38000원"
    assert restore_text(masked.field_hints["merchant"], masked.private_token_map) == "가상상점"
    assert "가상상점" not in masked.model_dump_json()


def test_invented_or_contradictory_text_is_rebuilt_from_input() -> None:
    original = ApprovalDraftProviderInput(
        request="인터뷰를 진행했습니다.\n승인하지 않았습니다.",
        answers=[],
        current_date=date(2026, 10, 30),
        timezone="Asia/Seoul",
    )
    for text in ("인터뷰를 진행했습니다.\n승인했습니다.", "인터뷰를 진행했습니다.\n예산 300만원"):
        candidate = ApprovalDraftCandidate(
            intent=DraftIntent.GENERAL, title="인터뷰 결과", content=text
        )
        result, status = verify_general_draft(candidate, original)
        assert status == "REBUILT_FROM_INPUT"
        assert result.content == original.request
        assert "300만원" not in result.content


def test_private_input_never_reaches_draft_or_embedding_provider(
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
        intent=DraftIntent.GENERAL,
        title="가짜 결재",
        content="승인받지 않은 지출 300만원",
        amount=300000,
    )
    login(client, "seojin.yoon@jhworks.test")
    secret = "가상인물123"
    response = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={
            "request": f"인터뷰 담당자 {secret} 연락처 010-0000-0000",
            "answers": ["가상회사987 관련 업무입니다."],
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["generalVerification"] == "NATURAL_INPUT_MATCHED"
    assert secret in data["preview"]["content"]
    assert "300만원" not in data["preview"]["content"]
    assert data["preview"]["amount"] is None
    assert data["candidate"]["amount"] is None
    outbound = fake_draft_provider.inputs[-1].model_dump_json()
    for item in (secret, "010-0000-0000", "가상회사987"):
        assert item not in outbound
        assert all(item not in text for text in fake_embedding_provider.texts)


def test_provider_rejects_unmasked_input_before_network() -> None:
    import pytest

    from app.ai.approval_draft import ApprovalDraftProviderError
    from app.ai.openai_approval_draft import OpenAIApprovalDraftProvider

    provider = OpenAIApprovalDraftProvider("not-a-real-key", "synthetic", 1)
    value = ApprovalDraftProviderInput(
        request="가상인물123 인터뷰",
        answers=[],
        current_date=date(2026, 10, 30),
        timezone="Asia/Seoul",
    )
    with pytest.raises(ApprovalDraftProviderError, match="Unmasked"):
        provider.prepare(value, "synthetic")


def test_example_search_rejects_user_text_before_embedding(
    session_factory: sessionmaker[Session], fake_embedding_provider: FakePolicyEmbeddingProvider
) -> None:
    import pytest

    from app.services.approval_examples import search_examples

    with session_factory() as db, pytest.raises(ValueError, match="topic hints"):
        search_examples(db, fake_embedding_provider, "가상인물123 인터뷰", "model", 1536)
    assert fake_embedding_provider.texts == []


def test_general_verifier_rejects_omission_and_generated_headings() -> None:
    original = ApprovalDraftProviderInput(
        request="검토 요청\n아직 승인되지 않았습니다.",
        answers=[],
        current_date=date(2026, 10, 30),
        timezone="Asia/Seoul",
    )
    for content in ("검토 요청", "승인 결과\n검토 요청\n아직 승인되지 않았습니다."):
        candidate = ApprovalDraftCandidate(
            intent=DraftIntent.GENERAL, title="검토 요청", content=content
        )
        checked, status = verify_general_draft(candidate, original)
        assert status == "REBUILT_FROM_INPUT"
        assert checked.content == original.request
    valid = ApprovalDraftCandidate(
        intent=DraftIntent.GENERAL, title="검토 요청", content=original.request, amount=99999
    )
    checked, status = verify_general_draft(valid, original)
    assert status == "INPUT_MATCHED"
    assert checked.amount is None

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import ApprovalDraftCandidate, ApprovalDraftProviderInput, DraftIntent
from app.models.enums import ExpenseCategory
from app.services.expense_grounding import check_expense_input
from tests.conftest import FakeApprovalDraftProvider
from tests.test_approval_draft_ai import approval_count

TEXT = (
    "금액: 17만원; 지출일: 2026-08-24; 사용처: 코레일; 분류: 교통비; "
    "목적: CES 출장; 증빙 참조: RCP-001"
)


def candidate(**updates: Any) -> ApprovalDraftCandidate:
    fields: dict[str, Any] = dict(
        intent=DraftIntent.EXPENSE,
        amount=170000,
        expense_date=date(2026, 8, 24),
        merchant="코레일",
        expense_category=ExpenseCategory.TRANSPORTATION,
        expense_purpose="CES 출장",
        receipt_reference="RCP-001",
        title="지어낸 고객명",
        content="규정을 모두 준수했고 영수증도 검증됐습니다.",
    )
    return ApprovalDraftCandidate(**{**fields, **updates})


def inputs(text: str = TEXT, answers: list[str] | None = None) -> ApprovalDraftProviderInput:
    return ApprovalDraftProviderInput(
        request=text,
        answers=answers or [],
        current_date=date(2026, 8, 25),
        timezone="Asia/Seoul",
    )


def test_canonical_fields_have_exact_source_ranges_and_server_prose() -> None:
    result, report = check_expense_input(candidate(), inputs())
    assert report.status == "INPUT_MATCHED"
    for check in report.checks:
        assert check.status == "INPUT_MATCHED"
        assert check.source_index == 0
        assert check.start is not None and check.end is not None
        assert TEXT[check.start : check.end]
    assert result.title == "CES 출장 경비 정산"
    assert "규정" not in (result.content or "")
    assert "지어낸" not in (result.title or "")


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount", 180000),
        ("merchant", "지어낸 사용처"),
        ("expense_date", date(2026, 8, 23)),
        ("expense_purpose", "고객 접대"),
        ("receipt_reference", "INVENTED"),
        ("expense_category", ExpenseCategory.MEALS),
    ],
)
def test_unmatched_fact_is_cleared_and_cannot_be_signed(field: str, value: Any) -> None:
    result, report = check_expense_input(candidate(**{field: value}), inputs())
    assert getattr(result, field) is None
    assert report.status == "NEEDS_INPUT"
    assert next(c for c in report.checks if c.field == field).status == "UNVERIFIED"


def test_latest_explicit_answer_overrides_stale_value_but_ambiguous_money_does_not_pass() -> None:
    value = inputs(answers=["금액: 18만원; 사용처: 새 사용처"])
    result, report = check_expense_input(candidate(), value)
    assert result.amount is None and result.merchant is None
    updated, report = check_expense_input(candidate(amount=180000, merchant="새 사용처"), value)
    assert report.status == "INPUT_MATCHED"
    assert updated.amount == 180000
    _, report = check_expense_input(candidate(), inputs("17만원과 18만원 정산"))
    assert next(c for c in report.checks if c.field == "amount").status == "UNVERIFIED"


def test_trip_dates_negative_currency_and_unlabelled_corrections_fail_closed() -> None:
    result, _ = check_expense_input(
        candidate(), inputs("출장 기간 2026-08-24 코레일 CES 출장 교통비 -17만원 RCP-001")
    )
    assert result.expense_date is None and result.amount is None
    result, _ = check_expense_input(
        candidate(), inputs("17만원 코레일 교통비 CES 출장 2026-08-24 RCP-001 아니 수정해")
    )
    assert result.amount is None and result.merchant is None


def test_relative_payment_date_and_optional_receipt() -> None:
    value = inputs(TEXT.replace("2026-08-24", "어제"))
    result, report = check_expense_input(candidate(receipt_reference=None), value)
    assert result.expense_date == date(2026, 8, 24)
    assert report.status == "INPUT_MATCHED"
    result, report = check_expense_input(candidate(), inputs("17만원 경비 정산"))
    assert result.amount == 170000
    assert result.merchant is None and result.expense_date is None
    assert report.status == "NEEDS_INPUT"


def test_api_invented_complete_candidate_cannot_issue_preview_or_create_document(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_draft_provider: FakeApprovalDraftProvider,
    session_factory: sessionmaker[Session],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    fake_draft_provider.candidate = candidate()
    before = approval_count(session_factory)
    body = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": "CES 경비 17만원 정산"},
    ).json()
    assert body["status"] == "NEEDS_INPUT"
    assert body["preview"] is None and body["confirmationToken"] is None
    assert body["candidate"]["merchant"] is None
    assert body["grounding"]["status"] == "NEEDS_INPUT"
    assert approval_count(session_factory) == before


def test_unlabelled_later_correction_cannot_reuse_an_older_labelled_fact() -> None:
    result, report = check_expense_input(candidate(), inputs(answers=["아니 사용처 수정해줘"]))
    assert result.merchant is None
    assert report.status == "NEEDS_INPUT"


def test_literal_input_can_be_used_without_requiring_retyping_labels() -> None:
    value = inputs("2026-08-24 코레일 교통비 17만원 CES 출장 RCP-001 정산")
    _, report = check_expense_input(candidate(), value)
    assert report.status == "INPUT_MATCHED"

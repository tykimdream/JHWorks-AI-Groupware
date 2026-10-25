import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.approval_draft import ApprovalDraftCandidate, DraftIntent
from app.evals.draft_contract import (
    ApprovalDraftEvalCase,
    catalog_report,
    grade_candidate,
    load_cases,
)
from app.evals.suite import load_manifest


def expense_case() -> ApprovalDraftEvalCase:
    return next(case for case in load_cases() if case.id == "past-spend-is-expense")


@pytest.mark.parametrize(
    ("updates", "failed_check"),
    [
        ({"intent": DraftIntent.BUSINESS_TRIP}, "intent"),
        ({"amount": 170000}, "amount"),
        ({"expense_date": date(2026, 8, 24)}, "expense_date"),
        ({"merchant": "추정한 사용처"}, "merchant"),
        ({"receipt_reference": "MADE-UP"}, "receipt_reference"),
    ],
)
def test_scoring_rejects_wrong_intent_amount_and_invented_facts(
    updates: dict[str, object],
    failed_check: str,
) -> None:
    # Explicit synthetic provider result, not a prediction generated from expected_values.
    candidate = ApprovalDraftCandidate.model_validate(
        {"intent": "EXPENSE", "amount": 500000, **updates}
    )
    result = grade_candidate(expense_case(), candidate)
    assert result.passed is False
    if failed_check == "intent":
        assert result.intent_check is False
    elif failed_check == "amount":
        assert result.value_checks[failed_check] is False
    else:
        assert result.null_checks[failed_check] is False


def test_scoring_accepts_facts_without_demanding_generated_prose_wording() -> None:
    candidate = ApprovalDraftCandidate(
        intent=DraftIntent.EXPENSE,
        amount=500000,
        title="출장 경비 정산",
        content="제공된 지출액을 기준으로 작성한 합성 초안입니다.",
    )
    assert grade_candidate(expense_case(), candidate).passed is True


@pytest.mark.parametrize("lodging,passed", [(None, True), (0, True), (1, False)])
def test_null_or_zero_is_distinct_from_unknown_facts(lodging: int | None, passed: bool) -> None:
    case = next(case for case in load_cases() if case.id == "multi-turn-business-trip-cost")
    candidate = ApprovalDraftCandidate(
        intent=DraftIntent.BUSINESS_TRIP,
        destination="서울",
        start_date=date(2026, 9, 15),
        end_date=date(2026, 9, 15),
        amount=90000,
        transportation=60000,
        meals=30000,
        client_name="테크포럼",
        lodging=lodging,
    )
    assert grade_candidate(case, candidate).passed is passed


@pytest.mark.parametrize(
    "updates",
    [
        {"expected_null_fields": ["merhcant"]},
        {"expected_null_fields": ["amount"]},
        {"expected_null_fields": ["merchant", "merchant"]},
        {"expected_null_or_zero_fields": ["merchant"]},
        {"expected_values": {"amount": "500000"}},
        {"expected_values": {"amount": True}},
        {"expected_values": {"expense_date": "2026-02-30"}},
    ],
)
def test_gold_contract_rejects_typo_overlap_and_impossible_expectations(
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ApprovalDraftEvalCase.model_validate({**expense_case().model_dump(), **updates})


def test_dataset_rejects_duplicate_ids_and_empty_catalog(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    case = expense_case().model_dump(mode="json")
    path.write_text(json.dumps([case, case]), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_cases(path)
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty"):
        load_cases(path)


def test_required_model_gate_matches_catalog_and_categories_are_present() -> None:
    cases = load_cases()
    gate = next(item for item in load_manifest().capabilities if item.name == "approval-draft")
    assert gate.required_case_ids == [case.id for case in cases if case.required]
    assert {case.category for case in cases} == {
        "intent",
        "amount",
        "date",
        "missing_facts",
        "follow_up",
        "trust_boundary",
    }
    assert len(cases) >= 30


def test_catalog_never_reports_model_quality_or_synthetic_latency() -> None:
    report = catalog_report()
    assert report["evaluationKind"] == "dataset-contract"
    assert report["modelEvaluationStatus"] == "not-run"
    assert report["providerCalls"] == 0
    assert report["modelPassRate"] is None
    assert report["modelTokens"] is None
    assert report["modelLatencyMs"] is None
    summary = report["summary"]
    assert isinstance(summary, dict)
    assert "passed" not in summary


def test_offline_command_cannot_import_settings_sdk_or_provider_factory() -> None:
    code = """
import json, sys
sys.modules['app.core.config'] = None
sys.modules['app.api.dependencies'] = None
sys.modules['openai'] = None
from app.evals.draft_contract import catalog_report
print(json.dumps(catalog_report()))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert json.loads(completed.stdout)["providerCalls"] == 0

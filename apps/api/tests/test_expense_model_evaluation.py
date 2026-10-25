import json
import stat
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, inspect

from app.ai.approval_draft import (
    ApprovalDraftCandidate,
    ApprovalDraftProviderError,
    DraftProviderUsage,
)
from app.ai.expense_pricing import MAX_REQUEST_MICRO_USD
from app.core.config import Settings
from app.ops import expense_model_evaluation as evaluation
from tests.test_budgeted_expense_draft import SyntheticProvider, result


def selected_plan() -> tuple[list[Any], dict[str, Any]]:
    cases, plan = evaluation.cases_and_plan()
    case = cases[0]
    plan.update(caseIds=[case.id], requiredIds=[case.id], maxProviderAttempts=1)
    return [case], plan


def test_plan_has_no_db_settings_or_sdk_imports() -> None:
    script = """
import builtins, runpy
original = builtins.__import__
def checked(name, *args, **kwargs):
    if name.startswith(("openai", "app.core.config", "app.core.database")):
        raise AssertionError("plan imported paid runtime")
    return original(name, *args, **kwargs)
builtins.__import__ = checked
runpy.run_module("app.ops.expense_model_evaluation", run_name="__main__")
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).parents[1],
    )
    report = json.loads(completed.stdout)
    assert report["evaluationKind"] == "model-plan"
    assert report["providerAttempts"] == report["businessDataWrites"] == 0
    assert report["maxProviderAttempts"] == 36 and len(report["requiredIds"]) == 10
    assert report["modelPassRate"] is None and report["promotionEligible"] is False


def test_source_and_dataset_guard_rejects_uncommitted_or_unapproved_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, dataset = "a" * 40, "b" * 64
    report = {"sourceCommit": source, "datasetSha256": dataset}
    assert not evaluation.checked_source(report, None, dataset)
    assert not evaluation.checked_source(report, source, "wrong")
    monkeypatch.setattr(evaluation, "git", lambda *args: "")
    assert evaluation.checked_source(report, source, dataset)

    def dirty(*args: str) -> str:
        raise subprocess.CalledProcessError(1, "synthetic dirty source")

    monkeypatch.setattr(evaluation, "git", dirty)
    assert not evaluation.checked_source(report, source, dataset)


def test_evaluation_stops_at_first_quality_failure_without_claiming_full_accuracy() -> None:
    cases, report = evaluation.cases_and_plan()
    provider = SyntheticProvider()
    # The first required case is deliberately answered with a different intent.
    provider.output = replace(result(), candidate=ApprovalDraftCandidate(intent="UNSUPPORTED"))
    saved: list[str] = []
    evaluated = evaluation.evaluate_cases(
        cases, provider, report, lambda value: saved.append(value["status"])
    )
    assert evaluated["status"] == "quality-check-failed" and provider.calls == 1
    assert evaluated["gradedCount"] == 1 and evaluated["fullDatasetCompleted"] is False
    assert evaluated["promotionEligible"] is False and saved[-1] == "quality-check-failed"
    assert "candidate" not in evaluated["results"][0]


def test_execution_uses_persistent_local_only_budget_and_private_atomic_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ai import openai_approval_draft
    from app.core import config

    cases, plan = selected_plan()
    provider = SyntheticProvider(
        replace(
            result(),
            candidate=ApprovalDraftCandidate.model_validate(
                {
                    "intent": cases[0].expected_intent,
                    **cases[0].expected_values,
                }
            ),
        )
    )
    monkeypatch.setattr(evaluation, "cases_and_plan", lambda: (cases, dict(plan)))
    monkeypatch.setattr(evaluation, "checked_source", lambda *args: True)
    monkeypatch.setattr(evaluation, "DIRECTORY", tmp_path)
    monkeypatch.setattr(evaluation, "LEDGER", tmp_path / "budget.sqlite3")
    monkeypatch.setattr(evaluation, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(evaluation, "MONTH_LIMIT_MICRO_USD", MAX_REQUEST_MICRO_USD)
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: Settings(_env_file=None, openai_api_key="synthetic-not-a-key"),
    )
    monkeypatch.setattr(
        openai_approval_draft, "OpenAIApprovalDraftProvider", lambda *args, **kwargs: provider
    )
    first = evaluation.run(execute=True)
    assert first["status"] == "passed" and first["providerAttempts"] == 1
    assert first["localMonthlyChargedMicroUsd"] == 1650
    second = evaluation.run(execute=True)
    assert second["status"] == "stopped" and second["errorCode"] == "AI_BUDGET_EXHAUSTED"
    assert second["providerAttempts"] == 0 and provider.calls == 1
    assert second["promotionEligible"] is False
    stored = json.loads(evaluation.REPORT.read_text())
    assert stored["status"] == "stopped" and "synthetic-not-a-key" not in json.dumps(stored)
    for path in (evaluation.LEDGER, evaluation.REPORT):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    engine = create_engine("sqlite:///" + str(evaluation.LEDGER))
    try:
        assert set(inspect(engine).get_table_names()) == {
            "ai_budget_counters",
            "ai_budget_reservations",
        }
    finally:
        engine.dispose()


def test_provider_diagnostics_are_not_saved_or_printed() -> None:
    cases, report = selected_plan()

    class FailedProvider(SyntheticProvider):
        def prepare(self, *args: Any, **kwargs: Any) -> Any:
            raise ApprovalDraftProviderError("private synthetic diagnostic")

    failed = evaluation.evaluate_cases(cases, FailedProvider(), report, lambda value: None)
    assert failed["status"] == "stopped" and failed["modelPassRate"] is None
    assert "private synthetic diagnostic" not in json.dumps(failed)


def test_per_run_cost_guard_survives_calendar_rollover_independently_of_month_ledger() -> None:
    cases, plan = selected_plan()
    case = cases[0]
    repeated = [case.model_copy(update={"id": f"synthetic-{index}"}) for index in range(4)]
    provider = SyntheticProvider(
        replace(
            result(),
            candidate=ApprovalDraftCandidate.model_validate(
                {
                    "intent": case.expected_intent,
                    **case.expected_values,
                }
            ),
            usage=DraftProviderUsage(400000, 1600, 401600),
        )
    )
    report = evaluation.evaluate_cases(repeated, provider, plan, lambda value: None)
    assert report["errorCode"] == "EVAL_RUN_BUDGET_EXHAUSTED"
    assert provider.calls == 3 and report["pricedResponsesMicroUsd"] == 921600
    assert report["fullDatasetCompleted"] is False and report["promotionEligible"] is False


def test_local_accounting_lock_and_partial_reports_are_excluded_from_git() -> None:
    paths = [
        "artifacts/evals/expense-model-ledger.sqlite3",
        "artifacts/evals/expense-model-ledger.sqlite3-journal",
        "artifacts/evals/expense-model.lock",
        "artifacts/evals/temporary-report.json",
    ]
    completed = subprocess.run(
        ["git", "check-ignore", "--no-index", *paths],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
        check=True,
    )
    assert set(completed.stdout.splitlines()) == set(paths)

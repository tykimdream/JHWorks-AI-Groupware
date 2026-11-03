"""Bounded synthetic evaluation. Default: plan only, no credentials/DB/provider imports."""

import argparse
import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.ai.approval_draft import (
    PROMPT_VERSION,
    ApprovalDraftProvider,
    ApprovalDraftProviderError,
    ApprovalDraftProviderInput,
    DraftProviderResult,
)
from app.ai.expense_pricing import MAX_REQUEST_MICRO_USD, MODEL, PRICE_VERSION, micro_usd
from app.evals.draft_contract import (
    DATASET_PATH,
    ApprovalDraftEvalCase,
    grade_candidate,
    load_cases,
)
from app.evals.expense_challenge import CHALLENGE_PATH

ROOT = Path(__file__).resolve().parents[4]
DIRECTORY = ROOT / "artifacts/evals"
LEDGER = DIRECTORY / "expense-model-ledger.sqlite3"
REPORT = DIRECTORY / "expense-model-evaluation.json"
MONTH_LIMIT_MICRO_USD = 1_000_000
RUN_LIMIT_MICRO_USD = 1_000_000
MAX_CASES = 36
RUNTIME_PATHS = (
    "apps/api/app/ai",
    "apps/api/app/core",
    "apps/api/app/models",
    "apps/api/app/services/login_budget.py",
    "pyproject.toml",
    "apps/api/pyproject.toml",
    "uv.lock",
    "apps/api/app/evals",
    "apps/api/evals",
    "apps/api/app/services/ai_budget.py",
    "apps/api/app/ops/expense_model_evaluation.py",
)


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()


def cases_and_plan(challenge: bool = False) -> tuple[list[ApprovalDraftEvalCase], dict[str, Any]]:
    dataset = CHALLENGE_PATH if challenge else DATASET_PATH
    cases = sorted(load_cases(dataset), key=lambda case: not case.required)
    if challenge and len(cases) != 5:
        raise ValueError("Challenge dataset must contain exactly five cases")
    if len(cases) > MAX_CASES or any(
        len(answer) > 2000 for case in cases for answer in case.answers
    ):
        raise ValueError("Dataset exceeds the reviewed input/case bounds")
    return cases, {
        "mode": "plan",
        "evaluationKind": "model-plan",
        "status": "planned",
        "sourceCommit": git("rev-parse", "HEAD"),
        "datasetSha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "datasetKind": "challenge" if challenge else "standard",
        "promptVersion": PROMPT_VERSION,
        "priceVersion": PRICE_VERSION,
        "model": MODEL,
        "caseIds": [case.id for case in cases],
        "requiredIds": [case.id for case in cases if case.required],
        "maxProviderAttempts": len(cases),
        "providerAttempts": 0,
        "maxOutputTokensPerRequest": 1600,
        "automaticRetries": 0,
        "maximumReservationMicroUsd": MAX_REQUEST_MICRO_USD,
        "maximumLocalMonthlyMicroUsd": MONTH_LIMIT_MICRO_USD,
        "maximumRunMicroUsd": RUN_LIMIT_MICRO_USD,
        "pricedResponsesMicroUsd": 0,
        "stopOnFirstQualityFailure": True,
        "businessDataWrites": 0,
        "cloudChanges": 0,
        "fullDatasetCompleted": False,
        "promotionEligible": False,
        "modelPassRate": None,
        "results": [],
    }


def checked_source(report: dict[str, Any], source: str | None, dataset: str | None) -> bool:
    if source != report["sourceCommit"] or dataset != report["datasetSha256"]:
        return False
    if not source or not re.fullmatch(r"[a-f0-9]{40}", source):
        return False
    try:
        git("cat-file", "-e", "HEAD:apps/api/app/ops/expense_model_evaluation.py")
        git("diff", "--quiet", "HEAD", "--", *RUNTIME_PATHS)
    except subprocess.CalledProcessError:
        return False
    return True


def evaluate_cases(
    cases: list[ApprovalDraftEvalCase],
    provider: ApprovalDraftProvider,
    report: dict[str, Any],
    save: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    from app.core.errors import AppError

    report.update(status="running", evaluationKind="model", mode="execute")
    outcomes: list[dict[str, Any]] = []
    report["results"] = outcomes
    safety_id = hashlib.sha256(b"jhworks-fixed-expense-evaluation").hexdigest()
    for case in cases:
        if report["pricedResponsesMicroUsd"] + MAX_REQUEST_MICRO_USD > RUN_LIMIT_MICRO_USD:
            report.update(
                status="stopped", errorCode="EVAL_RUN_BUDGET_EXHAUSTED", stoppedAtCase=case.id
            )
            break
        save(report)
        try:
            result = provider.prepare(
                ApprovalDraftProviderInput(
                    request=case.request,
                    answers=case.answers,
                    current_date=case.current_date,
                    timezone="Asia/Seoul",
                ),
                safety_id,
            )
        except (ApprovalDraftProviderError, AppError) as exc:
            report["status"] = "stopped"
            report["errorCode"] = (
                exc.code if isinstance(exc, AppError) else "AI_PROVIDER_UNAVAILABLE"
            )
            report["stoppedAtCase"] = case.id
            break
        report["pricedResponsesMicroUsd"] += micro_usd(
            result.usage.input_tokens, result.usage.output_tokens
        )
        grade = grade_candidate(case, result.candidate)
        outcomes.append(
            {
                "id": case.id,
                "required": case.required,
                "passed": grade.passed,
                "intentCheck": grade.intent_check,
                "valueChecks": grade.value_checks,
                "nullChecks": grade.null_checks,
                "nullOrZeroChecks": grade.null_or_zero_checks,
                "model": result.model,
                "latencyMs": result.latency_ms,
                "inputTokens": result.usage.input_tokens,
                "outputTokens": result.usage.output_tokens,
                "totalTokens": result.usage.total_tokens,
            }
        )
        if not grade.passed:
            report.update(status="quality-check-failed", stoppedAtCase=case.id)
            break
    else:
        report["status"] = "passed"
    passed = sum(item["passed"] for item in outcomes)
    report.update(
        summary={"passed": passed, "total": len(cases)},
        gradedCount=len(outcomes),
        fullDatasetCompleted=len(outcomes) == len(cases),
        modelPassRate=passed / len(outcomes) if outcomes else None,
        promotionEligible=(report.get("datasetKind") != "challenge"
                           and len(outcomes) == len(cases) and passed == len(cases)),
    )
    save(report)
    return report


def run(
    *,
    execute: bool = False,
    expected_source: str | None = None,
    expected_dataset: str | None = None,
    challenge: bool = False,
    accounting_directory: Path | None = None,
) -> dict[str, Any]:
    cases, report = cases_and_plan(True) if challenge else cases_and_plan()
    if not execute:
        return report
    if not checked_source(report, expected_source, expected_dataset):
        return {**report, "status": "source-or-dataset-not-approved"}
    # Challenge runs must reuse the existing ledger and its lock, never create a fresh budget.
    directory = accounting_directory if challenge else DIRECTORY
    if challenge and (
        directory is None or not directory.is_absolute() or directory.is_symlink()
        or not directory.is_dir()
        or not (directory / LEDGER.name).is_file() or (directory / LEDGER.name).is_symlink()
    ):
        return {**report, "status": "existing-accounting-required"}
    assert directory is not None
    ledger = directory / LEDGER.name if challenge else LEDGER
    result_path = directory / "expense-challenge-evaluation.json" if challenge else REPORT
    from app.core.config import get_settings

    key = get_settings().openai_api_key
    if key is None or not key.get_secret_value().strip():
        return {**report, "status": "key-not-configured"}
    import fcntl
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import sessionmaker

    from app.ai.budgeted_expense_draft import BudgetedExpenseDraftProvider
    from app.ai.openai_approval_draft import OpenAIApprovalDraftProvider
    from app.core.ai_budget import AIBudgetLimits
    from app.core.database import Base
    from app.models.ai_budget import AIBudgetCounter
    from app.services.login_budget import database_seconds

    directory.mkdir(parents=True, exist_ok=True)
    if any(path.is_symlink() for path in (ledger, result_path, directory / "expense-model.lock")):
        return {**report, "status": "unsafe-artifact-path"}
    lock_fd = os.open(directory / "expense-model.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {**report, "status": "evaluation-already-running"}
        ledger_fd = os.open(ledger, os.O_RDWR if challenge else os.O_CREAT | os.O_RDWR, 0o600)
        os.close(ledger_fd)
        os.chmod(ledger, 0o600)
        engine = create_engine("sqlite:///" + str(ledger))
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

        def save(value: dict[str, Any]) -> None:
            from tempfile import NamedTemporaryFile

            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=directory, suffix=".json", delete=False
            ) as stream:
                temporary = Path(stream.name)
                try:
                    json.dump(value, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                except BaseException:
                    temporary.unlink(missing_ok=True)
                    raise
            try:
                os.replace(temporary, result_path)
            finally:
                temporary.unlink(missing_ok=True)

        def construct() -> ApprovalDraftProvider:
            inner = OpenAIApprovalDraftProvider(
                key.get_secret_value(),
                MODEL,
                20.0,
                max_retries=0,
                standard_tier=True,
            )

            class CountedProvider:
                def prepare(
                    self, value: ApprovalDraftProviderInput, safety_identifier: str
                ) -> DraftProviderResult:
                    report["providerAttempts"] += 1
                    save(report)
                    return inner.prepare(value, safety_identifier)

            return CountedProvider()

        try:
            if challenge:
                from sqlalchemy import inspect

                if not {"ai_budget_counters", "ai_budget_reservations"}.issubset(
                    inspect(engine).get_table_names()
                ):
                    return {**report, "status": "existing-accounting-required"}
            if not challenge:
                Base.metadata.create_all(
                    engine,
                    tables=[
                        Base.metadata.tables["ai_budget_counters"],
                        Base.metadata.tables["ai_budget_reservations"],
                    ],
                )
            provider = BudgetedExpenseDraftProvider(
                workspace_id="fixed-synthetic-evaluation",
                factory=factory,
                provider_factory=construct,
                limits=AIBudgetLimits(
                    day_micro_usd=MONTH_LIMIT_MICRO_USD,
                    month_micro_usd=MONTH_LIMIT_MICRO_USD,
                    day_admissions=MAX_CASES,
                    scope_day_admissions=MAX_CASES,
                    concurrent_requests=1,
                ),
                check_authorization=lambda db: None,
            )
            # Store accounting at this fixed checkout path across repeat runs; never use app DB.
            report.update(localAccounting=True, ledgerPath=str(ledger))
            result_report = evaluate_cases(cases, provider, report, save)
            with factory() as db:
                from datetime import UTC, datetime
                from zoneinfo import ZoneInfo

                now = datetime.fromtimestamp(database_seconds(db), UTC).astimezone(
                    ZoneInfo("Asia/Seoul")
                )
                month = db.get(AIBudgetCounter, f"month:{now:%Y-%m}")
                result_report["localAccountingMonth"] = f"{now:%Y-%m}"
                result_report["localMonthlyChargedMicroUsd"] = month.spent_micro_usd if month else 0
                result_report["localMonthlyReservedMicroUsd"] = (
                    month.reserved_micro_usd if month else 0
                )
            save(result_report)
            return result_report
        except SQLAlchemyError:
            report.update(status="ledger-unavailable", promotionEligible=False)
            save(report)
            return report
        finally:
            engine.dispose()
    finally:
        os.close(lock_fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-source")
    parser.add_argument("--expected-dataset-sha256")
    parser.add_argument("--challenge", action="store_true")
    parser.add_argument("--accounting-directory", type=Path)
    args = parser.parse_args()
    report = run(
        execute=args.execute,
        expected_source=args.expected_source,
        expected_dataset=args.expected_dataset_sha256,
        challenge=args.challenge,
        accounting_directory=args.accounting_directory,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"planned", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

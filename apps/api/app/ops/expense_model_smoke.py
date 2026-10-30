"""Two fixed synthetic model cases. Plan only by default; never writes business data."""

import argparse
import hashlib
import json
from typing import Any

from app.ai.approval_draft import ApprovalDraftProviderError, ApprovalDraftProviderInput
from app.ai.openai_approval_draft import OpenAIApprovalDraftProvider
from app.core.config import get_settings
from app.evals.draft_contract import grade_candidate, load_cases
from app.services.draft_privacy import mask_draft_input

CASE_IDS = ("past-spend-is-expense", "multi-turn-ces-expense")
MODEL = "gpt-5.4-mini"


def run(*, execute: bool) -> dict[str, Any]:
    cases = {case.id: case for case in load_cases()}
    selected = [cases[case_id] for case_id in CASE_IDS]
    report: dict[str, Any] = {
        "mode": "execute" if execute else "plan",
        "model": MODEL,
        "cases": list(CASE_IDS),
        "maxRequests": 2,
        "maxOutputTokensPerRequest": 1600,
        "automaticRetries": 0,
        "timeoutSecondsPerRequest": 20,
        "businessDataWrites": 0,
        "cloudChanges": 0,
        "attempted": 0,
    }
    if not execute:
        return report
    key = get_settings().openai_api_key
    if key is None or not key.get_secret_value():
        return {**report, "status": "key-not-configured"}
    provider = OpenAIApprovalDraftProvider(key.get_secret_value(), MODEL, 20, max_retries=0)
    results: list[dict[str, Any]] = []
    for case in selected:
        report["attempted"] += 1
        try:
            result = provider.prepare(
                mask_draft_input(
                    ApprovalDraftProviderInput(
                        request=case.request,
                        answers=case.answers,
                        current_date=case.current_date,
                        timezone="Asia/Seoul",
                    )
                ).value,
                hashlib.sha256(b"jhworks-synthetic-expense-smoke").hexdigest(),
            )
        except (ApprovalDraftProviderError, ValueError):
            # Never print SDK diagnostics, exceptions, credentials or provider output.
            return {**report, "status": "provider-failed", "results": results}
        passed = grade_candidate(case, result.candidate).passed
        results.append(
            {
                "case": case.id,
                "passed": passed,
                "model": result.model,
                "inputTokens": result.usage.input_tokens,
                "outputTokens": result.usage.output_tokens,
                "latencyMs": result.latency_ms,
            }
        )
        if not passed:
            return {**report, "status": "quality-check-failed", "results": results}
    return {**report, "status": "passed", "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Make up to two paid requests")
    args = parser.parse_args()
    report = run(execute=args.execute)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") in {None, "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

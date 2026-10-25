import hashlib
import json

from app.ai.approval_draft import (
    PROMPT_VERSION,
    ApprovalDraftProviderError,
    ApprovalDraftProviderInput,
)
from app.evals.draft_contract import (
    DATASET_PATH,
    ApprovalDraftEvalCase,
    grade_candidate,
    load_cases,
)

# Preserve existing dataset imports used by tooling and tests.
__all__ = ["DATASET_PATH", "ApprovalDraftEvalCase", "load_cases"]


def main() -> int:
    cases = load_cases()
    from app.api.dependencies import get_approval_draft_provider

    provider = get_approval_draft_provider()
    safety_identifier = hashlib.sha256(b"jhworks-approval-draft-eval").hexdigest()
    outcomes: list[dict[str, object]] = []

    for case in cases:
        try:
            result = provider.prepare(
                ApprovalDraftProviderInput(
                    request=case.request,
                    answers=case.answers,
                    current_date=case.current_date,
                    timezone="Asia/Seoul",
                ),
                safety_identifier,
            )
        except ApprovalDraftProviderError:
            print(
                "Approval draft evaluation requires JHWORKS_OPENAI_API_KEY. "
                "No application data was changed."
            )
            return 2

        candidate = result.candidate.model_dump(mode="json")
        grade = grade_candidate(case, result.candidate)
        outcomes.append(
            {
                "id": case.id,
                "passed": grade.passed,
                "expectedIntent": case.expected_intent.value,
                "actualIntent": result.candidate.intent.value,
                "valueChecks": grade.value_checks,
                "nullChecks": grade.null_checks,
                "nullOrZeroChecks": grade.null_or_zero_checks,
                "actualValues": {
                    field: candidate.get(field)
                    for field in set(case.expected_values)
                    | set(case.expected_null_fields)
                    | set(case.expected_null_or_zero_fields)
                },
                "latencyMs": result.latency_ms,
                "totalTokens": result.usage.total_tokens,
                "model": result.model,
            }
        )

    passed_count = sum(bool(outcome["passed"]) for outcome in outcomes)
    print(
        json.dumps(
            {
                "evaluationKind": "model",
                "datasetSha256": hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest(),
                "promptVersion": PROMPT_VERSION,
                "summary": {"passed": passed_count, "total": len(outcomes)},
                "results": outcomes,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if passed_count == len(outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())

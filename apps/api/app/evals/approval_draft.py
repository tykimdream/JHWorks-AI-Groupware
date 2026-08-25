import hashlib
import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.ai.approval_draft import (
    ApprovalDraftProviderError,
    ApprovalDraftProviderInput,
    DraftIntent,
)
from app.api.dependencies import get_approval_draft_provider

DATASET_PATH = Path(__file__).parents[2] / "evals" / "approval_draft_cases.json"


class ApprovalDraftEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    request: str
    answers: list[str] = Field(default_factory=list)
    current_date: date
    expected_intent: DraftIntent
    expected_values: dict[str, str | int]
    expected_null_fields: list[str] = Field(default_factory=list)


def load_cases() -> list[ApprovalDraftEvalCase]:
    raw = json.loads(DATASET_PATH.read_text())
    return [ApprovalDraftEvalCase.model_validate(item) for item in raw]


def main() -> int:
    provider = get_approval_draft_provider()
    safety_identifier = hashlib.sha256(b"jhworks-approval-draft-eval").hexdigest()
    outcomes: list[dict[str, object]] = []

    for case in load_cases():
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
        value_checks = {
            field: candidate.get(field) == expected
            for field, expected in case.expected_values.items()
        }
        null_checks = {
            field: candidate.get(field) is None for field in case.expected_null_fields
        }
        passed = (
            result.candidate.intent == case.expected_intent
            and all(value_checks.values())
            and all(null_checks.values())
        )
        outcomes.append(
            {
                "id": case.id,
                "passed": passed,
                "expectedIntent": case.expected_intent.value,
                "actualIntent": result.candidate.intent.value,
                "valueChecks": value_checks,
                "nullChecks": null_checks,
                "actualValues": {
                    field: candidate.get(field)
                    for field in set(case.expected_values) | set(case.expected_null_fields)
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

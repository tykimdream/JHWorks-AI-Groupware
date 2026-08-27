import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.ai.leave_assistant import (
    LeaveAssistantIntent,
    LeaveAssistantProviderError,
    LeaveAssistantProviderInput,
)
from app.api.dependencies import get_leave_assistant_provider

DATASET_PATH = Path(__file__).parents[2] / "evals" / "leave_assistant_cases.json"


class LeaveAssistantEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    request: str
    answers: list[str] = Field(default_factory=list)
    current_date: date
    expected_intent: LeaveAssistantIntent
    expected_start: date | None
    expected_end: date | None
    expected_days: Decimal | None


def load_cases() -> list[LeaveAssistantEvalCase]:
    raw = json.loads(DATASET_PATH.read_text())
    return [LeaveAssistantEvalCase.model_validate(item) for item in raw]


def main() -> int:
    provider = get_leave_assistant_provider()
    safety_identifier = hashlib.sha256(b"jhworks-leave-assistant-eval").hexdigest()
    outcomes: list[dict[str, object]] = []
    for case in load_cases():
        try:
            result = provider.structure(
                LeaveAssistantProviderInput(
                    request=case.request,
                    answers=case.answers,
                    current_date=case.current_date,
                    timezone="Asia/Seoul",
                ),
                safety_identifier,
            )
        except LeaveAssistantProviderError:
            print(
                "Leave assistant provider was unavailable or returned invalid output. "
                "No application data was changed."
            )
            return 2
        candidate = result.candidate
        passed = (
            candidate.intent == case.expected_intent
            and candidate.search_start == case.expected_start
            and candidate.search_end == case.expected_end
            and candidate.requested_days == case.expected_days
        )
        outcomes.append(
            {
                "id": case.id,
                "passed": passed,
                "actual": candidate.model_dump(mode="json"),
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

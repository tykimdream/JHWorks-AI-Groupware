"""Pure dataset and scoring contracts. No settings, DB, SDK, or provider construction."""

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

from app.ai.approval_draft import PROMPT_VERSION, ApprovalDraftCandidate, DraftIntent

DATASET_PATH = Path(__file__).parents[2] / "evals" / "approval_draft_cases.json"
Category = Literal["intent", "amount", "date", "missing_facts", "follow_up", "trust_boundary"]


class ApprovalDraftEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    category: Category
    required: bool = False
    request: str = Field(min_length=2, max_length=2000)
    answers: list[str] = Field(default_factory=list, max_length=8)
    current_date: date
    expected_intent: DraftIntent
    expected_values: dict[str, StrictStr | StrictInt]
    expected_null_fields: list[str] = Field(default_factory=list)
    expected_null_or_zero_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_expectations(self) -> Self:
        groups = [
            list(self.expected_values),
            self.expected_null_fields,
            self.expected_null_or_zero_fields,
        ]
        names = [name for group in groups for name in group]
        if len(names) != len(set(names)):
            raise ValueError("Expected fields must be unique and non-overlapping")
        known = set(ApprovalDraftCandidate.model_fields) - {"intent"}
        if set(names) - known:
            raise ValueError("Unknown candidate field in expectation")
        numeric = {"amount", "transportation", "lodging", "meals", "other"}
        if set(self.expected_null_or_zero_fields) - numeric:
            raise ValueError("Null-or-zero is only valid for numeric fields")
        # Reject impossible types/dates/amounts in gold values before any paid run.
        gold = ApprovalDraftCandidate.model_validate(
            {"intent": self.expected_intent, **self.expected_values}
        ).model_dump(mode="json")
        if any(gold[name] != value for name, value in self.expected_values.items()):
            raise ValueError("Gold values must use canonical candidate types and dates")
        return self


def load_cases(path: Path = DATASET_PATH) -> list[ApprovalDraftEvalCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Evaluation dataset must be a non-empty list")
    cases = [ApprovalDraftEvalCase.model_validate(item) for item in raw]
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Evaluation case IDs must be unique")
    return cases


class CandidateGrade(BaseModel):
    passed: bool
    intent_check: bool
    value_checks: dict[str, bool]
    null_checks: dict[str, bool]
    null_or_zero_checks: dict[str, bool]


def grade_candidate(
    case: ApprovalDraftEvalCase, candidate: ApprovalDraftCandidate
) -> CandidateGrade:
    values = candidate.model_dump(mode="json")
    intent = candidate.intent == case.expected_intent
    checks = {name: values[name] == expected for name, expected in case.expected_values.items()}
    nulls = {name: values[name] is None for name in case.expected_null_fields}
    optional = {
        name: values[name] is None or values[name] == 0
        for name in case.expected_null_or_zero_fields
    }
    return CandidateGrade(
        passed=intent and all(checks.values()) and all(nulls.values()) and all(optional.values()),
        intent_check=intent,
        value_checks=checks,
        null_checks=nulls,
        null_or_zero_checks=optional,
    )


def catalog_report(path: Path = DATASET_PATH) -> dict[str, object]:
    cases = load_cases(path)
    # Dataset validity is NOT model accuracy: no candidate is generated or replayed here.
    return {
        "schemaVersion": "1.0",
        "datasetSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "promptVersion": PROMPT_VERSION,
        "evaluationKind": "dataset-contract",
        "summary": {"status": "validated", "caseCount": len(cases)},
        "categories": dict(sorted(Counter(case.category for case in cases).items())),
        "requiredCaseIds": [case.id for case in cases if case.required],
        "providerCalls": 0,
        "businessDataWrites": 0,
        "modelEvaluationStatus": "not-run",
        "modelPassRate": None,
        "modelLatencyMs": None,
        "modelTokens": None,
    }


def main() -> int:
    print(json.dumps(catalog_report(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

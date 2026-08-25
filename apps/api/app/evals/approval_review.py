import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.ai.approval_review import (
    ApprovalReviewProviderError,
    ReviewCategory,
    ReviewDocument,
    ReviewSeverity,
)
from app.api.dependencies import get_approval_review_provider

DATASET_PATH = Path(__file__).parents[2] / "evals" / "approval_review_cases.json"


class ApprovalReviewEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    document: ReviewDocument
    expected_categories: list[ReviewCategory]
    expect_no_blocking_issue: bool = False


def load_cases() -> list[ApprovalReviewEvalCase]:
    raw = json.loads(DATASET_PATH.read_text())
    return [ApprovalReviewEvalCase.model_validate(item) for item in raw]


def main() -> int:
    provider = get_approval_review_provider()
    safety_identifier = hashlib.sha256(b"jhworks-approval-review-eval").hexdigest()
    results: list[dict[str, object]] = []

    for case in load_cases():
        try:
            result = provider.review(case.document, safety_identifier)
        except ApprovalReviewProviderError:
            print(
                "AI review evaluation requires JHWORKS_OPENAI_API_KEY. "
                "No application data was changed."
            )
            return 2

        detected = {issue.category for issue in result.output.issues}
        expected = set(case.expected_categories)
        has_blocking_issue = any(
            issue.severity in {ReviewSeverity.MEDIUM, ReviewSeverity.HIGH}
            for issue in result.output.issues
        )
        passed = expected.issubset(detected) and not (
            case.expect_no_blocking_issue and has_blocking_issue
        )
        results.append(
            {
                "id": case.id,
                "passed": passed,
                "expectedCategories": sorted(category.value for category in expected),
                "detectedCategories": sorted(category.value for category in detected),
                "issueCount": len(result.output.issues),
                "latencyMs": result.latency_ms,
                "totalTokens": result.usage.total_tokens,
                "model": result.model,
            }
        )

    passed_count = sum(bool(item["passed"]) for item in results)
    print(
        json.dumps(
            {
                "summary": {"passed": passed_count, "total": len(results)},
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if passed_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

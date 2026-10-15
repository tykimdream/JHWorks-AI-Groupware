import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

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
    expected_category_groups: list[list[ReviewCategory]] = Field(default_factory=list)
    minimum_issue_count: int = Field(default=0, ge=0)
    forbidden_revision_phrases: list[str] = Field(default_factory=list)
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
        expected_groups = [set(group) for group in case.expected_category_groups]
        has_blocking_issue = any(
            issue.severity in {ReviewSeverity.MEDIUM, ReviewSeverity.HIGH}
            for issue in result.output.issues
        )
        has_editable_revision = bool(result.output.revised_content.strip()) and (
            not result.output.issues
            or result.output.revised_content.strip() != case.document.content.strip()
        )
        category_groups_match = all(detected & group for group in expected_groups)
        forbidden_revision_match = not any(
            phrase in result.output.revised_content
            for phrase in case.forbidden_revision_phrases
        )
        passed = (
            category_groups_match
            and len(result.output.issues) >= case.minimum_issue_count
            and has_editable_revision
            and forbidden_revision_match
            and not (case.expect_no_blocking_issue and has_blocking_issue)
        )
        results.append(
            {
                "id": case.id,
                "passed": passed,
                "expectedCategoryGroups": [
                    sorted(category.value for category in group)
                    for group in expected_groups
                ],
                "detectedCategories": sorted(category.value for category in detected),
                "issueCount": len(result.output.issues),
                "hasEditableRevision": has_editable_revision,
                "forbiddenRevisionPhraseFound": not forbidden_revision_match,
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

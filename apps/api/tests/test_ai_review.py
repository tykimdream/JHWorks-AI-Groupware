from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_review import (
    ProviderReviewResult,
    ReviewCategory,
    ReviewDocument,
    ReviewField,
    ReviewSeverity,
    SemanticReviewIssue,
    SemanticReviewOutput,
    UnavailableApprovalReviewProvider,
)
from app.api.dependencies import get_approval_review_provider
from app.evals.approval_review import load_cases
from app.main import app
from app.models.approval import Approval
from tests.conftest import FakeApprovalReviewProvider


def trip_payload() -> dict[str, Any]:
    return {
        "type": "BUSINESS_TRIP",
        "title": "부산 고객사 구현 범위 협의",
        "content": "고객사 담당자와 구현 범위와 다음 단계의 담당자를 합의합니다.",
        "amount": 350000,
        "details": {
            "kind": "BUSINESS_TRIP",
            "destination": "부산",
            "startDate": "2026-09-01",
            "endDate": "2026-09-02",
            "costBreakdown": {
                "transportation": 100000,
                "lodging": 120000,
                "meals": 80000,
                "other": 50000,
            },
            "clientName": "Orbit Retail Lab",
            "visitPurpose": "파일럿 구현 범위와 이해관계자별 책임을 확정합니다.",
        },
        "attachmentMetadata": [],
    }


def create_draft(client: TestClient, login: Callable[[TestClient, str], None]) -> dict[str, Any]:
    login(client, "seojin.yoon@jhworks.test")
    response = client.post("/api/v1/approvals", json=trip_payload())
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def test_ai_review_returns_structured_semantic_findings(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_review_provider: FakeApprovalReviewProvider,
) -> None:
    draft = create_draft(client, login)
    fake_review_provider.output = SemanticReviewOutput(
        issues=[
            SemanticReviewIssue(
                severity=ReviewSeverity.MEDIUM,
                category=ReviewCategory.CLARITY,
                field=ReviewField.CONTENT,
                message="출장 후 기대 결과가 더 구체적이면 좋습니다.",
                suggestion="합의할 산출물을 명시하세요.",
            )
        ],
        revised_content="고객사 담당자와 구현 범위, 산출물과 담당자를 확정합니다.",
    )

    response = client.post(
        f"/api/v1/approvals/{draft['id']}/ai-review",
        json={"version": draft["version"]},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "NEEDS_REVISION"
    assert result["score"] == 85
    assert result["issues"][0]["source"] == "LLM"
    assert result["issues"][0]["code"] == "LLM_CLARITY_1"
    assert result["provider"] == "fake"
    assert result["usage"]["totalTokens"] == 160
    assert result["isStale"] is False
    assert fake_review_provider.documents[0].type == "BUSINESS_TRIP"
    assert fake_review_provider.safety_identifiers[0] != "emp_sales_001"


def test_ai_review_passes_clear_document(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    draft = create_draft(client, login)
    response = client.post(
        f"/api/v1/approvals/{draft['id']}/ai-review",
        json={"version": draft["version"]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "PASS"
    assert response.json()["score"] == 100


def test_deterministic_review_detects_amount_mismatch(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    payload = trip_payload()
    payload["amount"] = 400000
    draft = client.post("/api/v1/approvals", json=payload).json()

    response = client.post(
        f"/api/v1/approvals/{draft['id']}/ai-review",
        json={"version": draft["version"]},
    )

    assert response.status_code == 200
    issue = response.json()["issues"][0]
    assert issue["code"] == "AMOUNT_BREAKDOWN_MISMATCH"
    assert issue["source"] == "DETERMINISTIC"
    assert response.json()["score"] == 75


def test_only_draft_author_can_request_ai_review(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    draft = create_draft(client, login)
    submitted = client.post(
        f"/api/v1/approvals/{draft['id']}/submit",
        json={"version": draft["version"]},
    ).json()

    response = client.post(
        f"/api/v1/approvals/{draft['id']}/ai-review",
        json={"version": submitted["version"]},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATUS"

    client.post("/api/v1/auth/logout")
    login(client, "doyun.choi@jhworks.test")
    response = client.post(
        f"/api/v1/approvals/{draft['id']}/ai-review",
        json={"version": submitted["version"]},
    )
    assert response.status_code == 403


def test_ai_review_rejects_stale_request_version(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    draft = create_draft(client, login)
    updated = trip_payload() | {"version": draft["version"]}
    changed = client.patch(f"/api/v1/approvals/{draft['id']}", json=updated)
    assert changed.status_code == 200

    response = client.post(
        f"/api/v1/approvals/{draft['id']}/ai-review",
        json={"version": draft["version"]},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_provider_failure_does_not_change_approval(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_review_provider: FakeApprovalReviewProvider,
) -> None:
    draft = create_draft(client, login)
    fake_review_provider.should_fail = True

    response = client.post(
        f"/api/v1/approvals/{draft['id']}/ai-review",
        json={"version": draft["version"]},
    )
    unchanged = client.get(f"/api/v1/approvals/{draft['id']}")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_REVIEW_UNAVAILABLE"
    assert unchanged.json()["version"] == draft["version"]
    assert unchanged.json()["status"] == "DRAFT"


def test_missing_provider_configuration_fails_safely(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    draft = create_draft(client, login)
    fake_override = app.dependency_overrides[get_approval_review_provider]
    app.dependency_overrides[get_approval_review_provider] = UnavailableApprovalReviewProvider
    try:
        response = client.post(
            f"/api/v1/approvals/{draft['id']}/ai-review",
            json={"version": draft["version"]},
        )
    finally:
        app.dependency_overrides[get_approval_review_provider] = fake_override

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_REVIEW_UNAVAILABLE"


def test_review_marks_result_stale_when_document_changes_during_call(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
) -> None:
    draft = create_draft(client, login)

    class MutatingProvider(FakeApprovalReviewProvider):
        def review(
            self,
            document: ReviewDocument,
            safety_identifier: str,
        ) -> ProviderReviewResult:
            with session_factory() as db:
                approval = db.get(Approval, draft["id"])
                assert approval is not None
                approval.version += 1
                db.commit()
            return super().review(document, safety_identifier)

    previous_override = app.dependency_overrides[get_approval_review_provider]
    app.dependency_overrides[get_approval_review_provider] = MutatingProvider
    try:
        response = client.post(
            f"/api/v1/approvals/{draft['id']}/ai-review",
            json={"version": draft["version"]},
        )
    finally:
        app.dependency_overrides[get_approval_review_provider] = previous_override

    assert response.status_code == 200
    assert response.json()["isStale"] is True
    assert response.json()["currentApprovalVersion"] == draft["version"] + 1


def test_ai_review_eval_dataset_covers_safety_and_quality() -> None:
    cases = load_cases()
    case_ids = {case.id for case in cases}

    assert len(cases) >= 6
    assert "clear-business-trip" in case_ids
    assert "synthetic-personal-data" in case_ids
    assert "prompt-injection-in-document" in case_ids

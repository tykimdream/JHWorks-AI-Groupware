import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.approval_review import (
    PROMPT_VERSION,
    ApprovalReviewProvider,
    ApprovalReviewProviderError,
    ProviderReviewResult,
    ReviewCategory,
    ReviewDocument,
    ReviewField,
    ReviewSeverity,
)
from app.core.errors import (
    AuthorizationError,
    ConflictError,
    ServiceUnavailableError,
)
from app.models.approval import Approval
from app.models.employee import Employee
from app.models.enums import ApprovalStatus, ApprovalType
from app.schemas.ai_review import (
    AIReviewIssue,
    AIReviewResponse,
    AIReviewUsage,
    ReviewSource,
    ReviewStatus,
)
from app.services import approval as approval_service

logger = logging.getLogger("jhworks.ai_review")

SEVERITY_PENALTIES = {
    ReviewSeverity.INFO: 0,
    ReviewSeverity.LOW: 8,
    ReviewSeverity.MEDIUM: 15,
    ReviewSeverity.HIGH: 25,
}


def _issue(
    code: str,
    severity: ReviewSeverity,
    category: ReviewCategory,
    field: ReviewField,
    message: str,
    suggestion: str,
) -> AIReviewIssue:
    return AIReviewIssue(
        code=code,
        source=ReviewSource.DETERMINISTIC,
        severity=severity,
        category=category,
        field=field,
        message=message,
        suggestion=suggestion,
    )


def deterministic_review(approval: Approval) -> list[AIReviewIssue]:
    issues: list[AIReviewIssue] = []

    if not approval.content.strip():
        issues.append(
            _issue(
                "CONTENT_REQUIRED",
                ReviewSeverity.HIGH,
                ReviewCategory.COMPLETENESS,
                ReviewField.CONTENT,
                "업무 내용이 비어 있습니다.",
                "결재 목적과 기대 결과를 작성하세요.",
            )
        )

    if approval.type != ApprovalType.BUSINESS_TRIP:
        return issues

    details = approval.details
    required = (
        ("destination", "DESTINATION_REQUIRED", ReviewField.DESTINATION, "출장지를 입력하세요."),
        ("startDate", "START_DATE_REQUIRED", ReviewField.START_DATE, "출장 시작일을 입력하세요."),
        ("endDate", "END_DATE_REQUIRED", ReviewField.END_DATE, "출장 종료일을 입력하세요."),
        (
            "clientName",
            "CLIENT_NAME_REQUIRED",
            ReviewField.CLIENT_NAME,
            "방문할 고객사를 입력하세요.",
        ),
        (
            "visitPurpose",
            "VISIT_PURPOSE_REQUIRED",
            ReviewField.VISIT_PURPOSE,
            "고객사 방문 목적을 입력하세요.",
        ),
    )
    for key, code, field, message in required:
        value = details.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            issues.append(
                _issue(
                    code,
                    ReviewSeverity.HIGH,
                    ReviewCategory.COMPLETENESS,
                    field,
                    message,
                    "제출 전에 필수 정보를 채우세요.",
                )
            )

    start_date = details.get("startDate")
    end_date = details.get("endDate")
    if isinstance(start_date, str) and isinstance(end_date, str) and start_date > end_date:
        issues.append(
            _issue(
                "INVALID_DATE_ORDER",
                ReviewSeverity.HIGH,
                ReviewCategory.COMPLETENESS,
                ReviewField.END_DATE,
                "출장 종료일이 시작일보다 빠릅니다.",
                "출장 기간을 다시 확인하세요.",
            )
        )

    if approval.amount is None:
        issues.append(
            _issue(
                "AMOUNT_REQUIRED",
                ReviewSeverity.HIGH,
                ReviewCategory.COMPLETENESS,
                ReviewField.AMOUNT,
                "출장 예상 금액이 없습니다.",
                "예상 비용의 총액을 입력하세요.",
            )
        )

    breakdown = details.get("costBreakdown")
    if isinstance(breakdown, dict):
        values = [value for value in breakdown.values() if isinstance(value, int)]
        if values and approval.amount is not None and sum(values) != approval.amount:
            issues.append(
                _issue(
                    "AMOUNT_BREAKDOWN_MISMATCH",
                    ReviewSeverity.HIGH,
                    ReviewCategory.COMPLETENESS,
                    ReviewField.COST_BREAKDOWN,
                    "예상 금액과 비용 세부 내역의 합계가 일치하지 않습니다.",
                    "교통비, 숙박비, 식비와 기타 비용의 합계를 확인하세요.",
                )
            )
    elif approval.amount is not None:
        issues.append(
            _issue(
                "COST_BREAKDOWN_REQUIRED",
                ReviewSeverity.MEDIUM,
                ReviewCategory.COMPLETENESS,
                ReviewField.COST_BREAKDOWN,
                "예상 금액의 비용 세부 내역이 없습니다.",
                "교통비, 숙박비, 식비와 기타 비용을 구분해 작성하세요.",
            )
        )

    return issues


def _merge_issues(
    deterministic: list[AIReviewIssue],
    provider_result: ProviderReviewResult,
) -> list[AIReviewIssue]:
    issues = list(deterministic)
    seen = {(issue.category, issue.field) for issue in deterministic}
    category_counts: dict[ReviewCategory, int] = {}
    for semantic in provider_result.output.issues:
        key = (semantic.category, semantic.field)
        if key in seen:
            continue
        seen.add(key)
        category_counts[semantic.category] = category_counts.get(semantic.category, 0) + 1
        issues.append(
            AIReviewIssue(
                code=f"LLM_{semantic.category.value}_{category_counts[semantic.category]}",
                source=ReviewSource.LLM,
                severity=semantic.severity,
                category=semantic.category,
                field=semantic.field,
                message=semantic.message.strip(),
                suggestion=(semantic.suggestion or "").strip() or None,
            )
        )
    return issues


def review_approval(
    db: Session,
    actor: Employee,
    approval_id: str,
    expected_version: int,
    provider: ApprovalReviewProvider,
) -> AIReviewResponse:
    approval = approval_service.get_approval(db, actor, approval_id)
    if approval.author_id != actor.id:
        raise AuthorizationError("Only the approval author can request an AI review")
    if approval.status != ApprovalStatus.DRAFT:
        raise ConflictError("INVALID_STATUS", "Only draft approvals can be reviewed")
    if approval.version != expected_version:
        raise ConflictError(
            "VERSION_CONFLICT",
            "The approval changed after it was loaded. Refresh and try again.",
        )

    deterministic = deterministic_review(approval)
    document = ReviewDocument(
        type=approval.type.value,
        title=approval.title,
        content=approval.content,
        amount=approval.amount,
        details=approval.details,
        attachment_metadata=approval.attachment_metadata,
        deterministic_findings=[issue.code for issue in deterministic],
    )
    safety_identifier = hashlib.sha256(actor.id.encode()).hexdigest()

    try:
        provider_result = provider.review(document, safety_identifier)
    except ApprovalReviewProviderError as exc:
        logger.warning(
            "ai_review_failed actor_id=%s approval_id=%s prompt_version=%s",
            actor.id,
            approval.id,
            PROMPT_VERSION,
        )
        raise ServiceUnavailableError(
            "AI_REVIEW_UNAVAILABLE",
            "AI review is temporarily unavailable. The approval was not changed.",
        ) from exc

    issues = _merge_issues(deterministic, provider_result)
    score = max(0, 100 - sum(SEVERITY_PENALTIES[issue.severity] for issue in issues))

    db.expire_all()
    latest = db.scalar(select(Approval).where(Approval.id == approval_id))
    current_version = latest.version if latest else expected_version
    is_stale = (
        latest is None
        or current_version != expected_version
        or latest.status != ApprovalStatus.DRAFT
    )

    status = ReviewStatus.NEEDS_REVISION if issues else ReviewStatus.PASS
    logger.info(
        "ai_review_completed actor_id=%s approval_id=%s approval_version=%s "
        "status=%s issue_count=%s provider=%s model=%s prompt_version=%s "
        "latency_ms=%s input_tokens=%s output_tokens=%s stale=%s",
        actor.id,
        approval_id,
        expected_version,
        status.value,
        len(issues),
        provider_result.provider,
        provider_result.model,
        PROMPT_VERSION,
        provider_result.latency_ms,
        provider_result.usage.input_tokens,
        provider_result.usage.output_tokens,
        is_stale,
    )
    revised_content = (provider_result.output.revised_content or "").strip() or None
    return AIReviewResponse(
        approval_id=approval_id,
        approval_version=expected_version,
        current_approval_version=current_version,
        is_stale=is_stale,
        status=status,
        score=score,
        issues=issues,
        revised_content=revised_content,
        provider=provider_result.provider,
        model=provider_result.model,
        prompt_version=PROMPT_VERSION,
        usage=AIReviewUsage(
            input_tokens=provider_result.usage.input_tokens,
            output_tokens=provider_result.usage.output_tokens,
            total_tokens=provider_result.usage.total_tokens,
        ),
        latency_ms=provider_result.latency_ms,
        reviewed_at=datetime.now(UTC),
    )

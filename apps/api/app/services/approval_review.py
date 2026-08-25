import hashlib
import logging
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.ai.approval_review import (
    PROMPT_VERSION,
    ApprovalReviewProvider,
    ApprovalReviewProviderError,
    PolicyContextSection,
    ProviderReviewResult,
    ReviewCategory,
    ReviewDocument,
    ReviewField,
    ReviewSeverity,
)
from app.ai.policy_embedding import PolicyEmbeddingProvider
from app.core.config import get_settings
from app.core.errors import (
    AuthorizationError,
    ConflictError,
    ServiceUnavailableError,
)
from app.models.approval import Approval
from app.models.employee import Employee
from app.models.enums import ApprovalStatus, ApprovalType
from app.models.policy import PolicySection
from app.schemas.ai_review import (
    AIReviewIssue,
    AIReviewResponse,
    AIReviewUsage,
    PolicyReviewMetadata,
    ReviewSource,
    ReviewStatus,
)
from app.schemas.policy import (
    PolicyEmbeddingUsage,
    PolicyRetrievalStatus,
    PolicySearchResponse,
)
from app.services import approval as approval_service
from app.services import policy_retrieval

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
        citations=[],
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


def deterministic_policy_review(
    db: Session,
    approval: Approval,
    policy_search: PolicySearchResponse,
) -> tuple[list[AIReviewIssue], set[str]]:
    if policy_search.status != PolicyRetrievalStatus.READY or not policy_search.items:
        return [], set()

    citations_by_key = {item.citation_key: item for item in policy_search.items}
    section_ids = [item.section_id for item in policy_search.items]
    sections = db.scalars(
        select(PolicySection)
        .options(joinedload(PolicySection.policy))
        .where(PolicySection.section_id.in_(section_ids))
    )
    issues: list[AIReviewIssue] = []
    non_actionable_citation_keys: set[str] = set()
    for section in sections.unique():
        key = f"{section.policy.policy_id}:{section.policy.version}:{section.section_id}"
        citation = citations_by_key.get(key)
        rule = section.rule_config
        if citation is None or not isinstance(rule, dict):
            continue

        kind = rule.get("kind")
        if kind == "PRIOR_APPROVAL_MIN_TOTAL":
            non_actionable_citation_keys.add(key)

        if kind == "MAX_LODGING_PER_NIGHT":
            breakdown = approval.details.get("costBreakdown")
            lodging = breakdown.get("lodging") if isinstance(breakdown, dict) else None
            start = approval.details.get("startDate")
            end = approval.details.get("endDate")
            limit = rule.get("limitKrw")
            if not (
                isinstance(lodging, int)
                and isinstance(start, str)
                and isinstance(end, str)
                and isinstance(limit, int)
            ):
                continue
            try:
                nights = max(1, (date.fromisoformat(end) - date.fromisoformat(start)).days)
            except ValueError:
                continue
            allowed = limit * nights
            if lodging > allowed:
                issues.append(
                    AIReviewIssue(
                        code="POLICY_MAX_LODGING_PER_NIGHT",
                        source=ReviewSource.POLICY,
                        severity=ReviewSeverity.HIGH,
                        category=ReviewCategory.POLICY,
                        field=ReviewField.COST_BREAKDOWN,
                        message=(
                            f"숙박비 {lodging:,}원은 {nights}박 기준 한도 "
                            f"{allowed:,}원을 초과합니다."
                        ),
                        suggestion="숙박비를 한도 안으로 조정하거나 예외 승인 사유를 작성하세요.",
                        citations=[citation],
                    )
                )

        if kind == "ATTACHMENT_REQUIRED_WHEN_COST_POSITIVE":
            breakdown = approval.details.get("costBreakdown")
            cost_field = rule.get("costField")
            cost = (
                breakdown.get(cost_field)
                if isinstance(breakdown, dict) and isinstance(cost_field, str)
                else None
            )
            if isinstance(cost, int) and cost > 0 and not approval.attachment_metadata:
                issues.append(
                    AIReviewIssue(
                        code="POLICY_TRANSPORTATION_DOCUMENT_REQUIRED",
                        source=ReviewSource.POLICY,
                        severity=ReviewSeverity.MEDIUM,
                        category=ReviewCategory.POLICY,
                        field=ReviewField.ATTACHMENTS,
                        message="교통비 실비 정산을 확인할 증빙이 첨부되지 않았습니다.",
                        suggestion="교통비 영수증 또는 예약 내역을 첨부하세요.",
                        citations=[citation],
                    )
                )

        if kind == "RECEIPT_REQUIRED_MIN_TOTAL":
            threshold = rule.get("thresholdKrw")
            if (
                isinstance(threshold, int)
                and approval.amount is not None
                and approval.amount >= threshold
                and not approval.attachment_metadata
            ):
                issues.append(
                    AIReviewIssue(
                        code="POLICY_RECEIPT_REQUIRED",
                        source=ReviewSource.POLICY,
                        severity=ReviewSeverity.HIGH,
                        category=ReviewCategory.POLICY,
                        field=ReviewField.ATTACHMENTS,
                        message=f"{threshold:,}원 이상 경비에 필요한 영수증이 없습니다.",
                        suggestion="제출 전에 영수증을 첨부하세요.",
                        citations=[citation],
                    )
                )
    return issues, non_actionable_citation_keys


def _merge_issues(
    deterministic: list[AIReviewIssue],
    provider_result: ProviderReviewResult,
    policy_search: PolicySearchResponse,
    non_actionable_citation_keys: set[str],
) -> list[AIReviewIssue]:
    issues = list(deterministic)
    seen = {(issue.category, issue.field) for issue in deterministic}
    citations_by_key = {item.citation_key: item for item in policy_search.items}
    deterministic_fields = {issue.field for issue in deterministic}
    seen_policy = {
        (issue.field, tuple(citation.citation_key for citation in issue.citations))
        for issue in deterministic
        if issue.source == ReviewSource.POLICY
    }
    category_counts: dict[ReviewCategory, int] = {}
    for semantic in provider_result.output.issues:
        if semantic.category == ReviewCategory.RISK and semantic.severity != ReviewSeverity.HIGH:
            logger.warning("speculative_risk_issue_dropped severity=%s", semantic.severity.value)
            continue
        if semantic.field in deterministic_fields:
            logger.info("duplicate_semantic_issue_dropped field=%s", semantic.field.value)
            continue
        if semantic.category == ReviewCategory.COMPLETENESS and semantic.field not in {
            ReviewField.DOCUMENT,
            ReviewField.TITLE,
            ReviewField.CONTENT,
        }:
            logger.info("structured_completeness_issue_dropped field=%s", semantic.field.value)
            continue
        citations = []
        if semantic.category == ReviewCategory.POLICY:
            citation_keys = tuple(dict.fromkeys(semantic.citation_keys))
            if (
                not citation_keys
                or policy_search.status != PolicyRetrievalStatus.READY
                or any(key not in citations_by_key for key in citation_keys)
            ):
                logger.warning("unsupported_policy_issue_dropped citation_keys=%s", citation_keys)
                continue
            if set(citation_keys).issubset(non_actionable_citation_keys):
                logger.info("non_actionable_policy_issue_dropped citation_keys=%s", citation_keys)
                continue
            policy_key = (semantic.field, citation_keys)
            if policy_key in seen_policy:
                continue
            seen_policy.add(policy_key)
            citations = [citations_by_key[key] for key in citation_keys]
        elif semantic.citation_keys:
            logger.warning(
                "citations_removed_from_non_policy_issue category=%s",
                semantic.category.value,
            )

        key = (semantic.category, semantic.field)
        if semantic.category != ReviewCategory.POLICY and key in seen:
            continue
        if semantic.category != ReviewCategory.POLICY:
            seen.add(key)
        category_counts[semantic.category] = category_counts.get(semantic.category, 0) + 1
        code_prefix = (
            "POLICY"
            if semantic.category == ReviewCategory.POLICY
            else f"LLM_{semantic.category.value}"
        )
        issues.append(
            AIReviewIssue(
                code=f"{code_prefix}_{category_counts[semantic.category]}",
                source=(
                    ReviewSource.POLICY
                    if semantic.category == ReviewCategory.POLICY
                    else ReviewSource.LLM
                ),
                severity=semantic.severity,
                category=semantic.category,
                field=semantic.field,
                message=semantic.message.strip(),
                suggestion=(semantic.suggestion or "").strip() or None,
                citations=citations,
            )
        )
    return issues


def _not_applicable_policy_search() -> PolicySearchResponse:
    return PolicySearchResponse(
        status=PolicyRetrievalStatus.NOT_APPLICABLE,
        items=[],
        provider=None,
        model=None,
        usage=PolicyEmbeddingUsage(input_tokens=0, total_tokens=0),
        latency_ms=0,
    )


def review_approval(
    db: Session,
    actor: Employee,
    approval_id: str,
    expected_version: int,
    provider: ApprovalReviewProvider,
    embedding_provider: PolicyEmbeddingProvider,
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
    settings = get_settings()
    policy_type = policy_retrieval.APPROVAL_POLICY_TYPES.get(approval.type)
    policy_search = (
        policy_retrieval.search_policy_sections(
            db=db,
            query=policy_retrieval.approval_policy_query(approval),
            policy_type=policy_type,
            top_k=settings.policy_retrieval_top_k,
            min_score=settings.policy_retrieval_min_score,
            provider=embedding_provider,
            expected_model=settings.policy_embedding_model,
            expected_dimensions=settings.policy_embedding_dimensions,
        )
        if policy_type is not None
        else _not_applicable_policy_search()
    )
    policy_issues, non_actionable_citation_keys = deterministic_policy_review(
        db, approval, policy_search
    )
    deterministic.extend(policy_issues)
    document = ReviewDocument(
        type=approval.type.value,
        title=approval.title,
        content=approval.content,
        amount=approval.amount,
        details=approval.details,
        attachment_metadata=approval.attachment_metadata,
        deterministic_findings=[issue.code for issue in deterministic],
        policy_context=[
            PolicyContextSection(
                citation_key=item.citation_key,
                policy_id=item.policy_id,
                policy_title=item.policy_title,
                policy_type=item.policy_type.value,
                version=item.version,
                section_id=item.section_id,
                section_title=item.section_title,
                content=item.excerpt,
            )
            for item in policy_search.items
        ],
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

    issues = _merge_issues(
        deterministic,
        provider_result,
        policy_search,
        non_actionable_citation_keys,
    )
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
    logger.info(
        "policy_review_completed approval_id=%s status=%s section_ids=%s model=%s "
        "latency_ms=%s input_tokens=%s",
        approval_id,
        policy_search.status.value,
        [item.section_id for item in policy_search.items],
        policy_search.model,
        policy_search.latency_ms,
        policy_search.usage.input_tokens,
    )
    revised_content = provider_result.output.revised_content.strip()
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
        policy_review=PolicyReviewMetadata(
            status=policy_search.status,
            retrieved_citations=policy_search.items,
            provider=policy_search.provider,
            model=policy_search.model,
            usage=policy_search.usage,
            latency_ms=policy_search.latency_ms,
        ),
        latency_ms=provider_result.latency_ms,
        reviewed_at=datetime.now(UTC),
    )

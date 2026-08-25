import hashlib
import logging
import math
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.policy_embedding import PolicyEmbeddingProvider, PolicyEmbeddingProviderError
from app.models.approval import Approval
from app.models.enums import ApprovalType, PolicyStatus, PolicyType
from app.models.policy import CompanyPolicy, PolicySection
from app.schemas.policy import (
    PolicyCitation,
    PolicyEmbeddingUsage,
    PolicyRetrievalStatus,
    PolicySearchResponse,
)

logger = logging.getLogger("jhworks.policy_retrieval")

APPROVAL_POLICY_TYPES: dict[ApprovalType, PolicyType] = {
    ApprovalType.BUSINESS_TRIP: PolicyType.TRAVEL,
    ApprovalType.EXPENSE: PolicyType.EXPENSE,
    ApprovalType.LEAVE: PolicyType.LEAVE,
}


def policy_search_text(policy: CompanyPolicy, section: PolicySection) -> str:
    return "\n".join(
        (
            f"Policy type: {policy.type.value}",
            f"Policy: {policy.title}",
            f"Version: {policy.version}",
            f"Section: {section.title}",
            section.content.strip(),
        )
    )


def _search_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _current_policies(db: Session, policy_type: PolicyType | None) -> list[CompanyPolicy]:
    statement = (
        select(CompanyPolicy)
        .options(selectinload(CompanyPolicy.sections))
        .where(
            CompanyPolicy.status == PolicyStatus.ACTIVE,
            CompanyPolicy.effective_from <= date.today(),
        )
        .order_by(
            CompanyPolicy.policy_id,
            CompanyPolicy.effective_from.desc(),
            CompanyPolicy.version.desc(),
        )
    )
    if policy_type is not None:
        statement = statement.where(CompanyPolicy.type == policy_type)

    latest: dict[str, CompanyPolicy] = {}
    for policy in db.scalars(statement).unique():
        latest.setdefault(policy.policy_id, policy)
    return list(latest.values())


def index_active_policy_sections(
    db: Session,
    provider: PolicyEmbeddingProvider,
    expected_model: str,
    expected_dimensions: int,
) -> tuple[int, int, str, int]:
    policies = _current_policies(db, None)
    pending: list[tuple[PolicySection, str, str]] = []
    skipped = 0
    for policy in policies:
        for section in policy.sections:
            text = policy_search_text(policy, section)
            content_hash = _search_text_hash(text)
            if (
                section.embedding is not None
                and section.embedding_model == expected_model
                and section.embedded_content_hash == content_hash
            ):
                skipped += 1
                continue
            pending.append((section, text, content_hash))

    if not pending:
        return 0, skipped, expected_model, 0

    result = provider.embed([text for _, text, _ in pending])
    if result.model != expected_model:
        raise PolicyEmbeddingProviderError("The embedding model did not match the index contract")
    if len(result.vectors) != len(pending) or any(
        len(vector) != expected_dimensions for vector in result.vectors
    ):
        raise PolicyEmbeddingProviderError(
            "The embedding dimensions did not match the index contract"
        )

    indexed_at = datetime.now(UTC)
    for (section, _, content_hash), vector in zip(pending, result.vectors, strict=True):
        section.embedding = vector
        section.embedding_model = result.model
        section.embedded_content_hash = content_hash
        section.indexed_at = indexed_at
    db.commit()

    logger.info(
        "policy_index_completed model=%s indexed=%s skipped=%s input_tokens=%s latency_ms=%s",
        result.model,
        len(pending),
        skipped,
        result.usage.input_tokens,
        result.latency_ms,
    )
    return len(pending), skipped, result.model, result.usage.total_tokens


def approval_policy_query(approval: Approval) -> str:
    details = approval.details
    parts = [
        f"Approval type: {approval.type.value}",
        f"Title: {approval.title}",
        f"Content: {approval.content}",
    ]
    if approval.amount is not None:
        parts.append(f"Estimated total amount: KRW {approval.amount}")
    for key in (
        "destination",
        "startDate",
        "endDate",
        "clientName",
        "visitPurpose",
    ):
        value = details.get(key)
        if value is not None and str(value).strip():
            parts.append(f"{key}: {value}")
    breakdown = details.get("costBreakdown")
    if isinstance(breakdown, dict):
        for key, value in breakdown.items():
            if isinstance(value, int):
                parts.append(f"{key}: KRW {value}")
    if approval.attachment_metadata:
        parts.append(
            "Attachments: "
            + ", ".join(item.get("name", "") for item in approval.attachment_metadata)
        )
    return "\n".join(parts)


def _is_current_index(
    policy: CompanyPolicy,
    section: PolicySection,
    expected_model: str,
) -> bool:
    return (
        section.embedding is not None
        and section.embedding_model == expected_model
        and section.embedded_content_hash
        == _search_text_hash(policy_search_text(policy, section))
    )


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return -1.0
    return dot / (left_norm * right_norm)


def _citation(section: PolicySection, score: float) -> PolicyCitation:
    policy = section.policy
    return PolicyCitation(
        citation_key=f"{policy.policy_id}:{policy.version}:{section.section_id}",
        policy_id=policy.policy_id,
        policy_title=policy.title,
        policy_type=policy.type,
        version=policy.version,
        section_id=section.section_id,
        section_title=section.title,
        excerpt=section.content[:1000],
        similarity_score=round(score, 6),
    )


def _rank_sections(
    db: Session,
    policies: list[CompanyPolicy],
    query_vector: list[float],
    top_k: int,
) -> list[tuple[PolicySection, float]]:
    record_ids = [policy.record_id for policy in policies]
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        embedding_column = cast(Any, PolicySection.embedding)
        distance = embedding_column.cosine_distance(query_vector)
        rows = db.execute(
            select(PolicySection, distance.label("distance"))
            .options(selectinload(PolicySection.policy))
            .where(PolicySection.policy_record_id.in_(record_ids))
            .order_by(distance)
            .limit(top_k)
        ).all()
        return [(section, 1.0 - float(distance_value)) for section, distance_value in rows]

    ranked: list[tuple[PolicySection, float]] = []
    for policy in policies:
        for section in policy.sections:
            if section.embedding is None:
                continue
            vector = [float(value) for value in section.embedding]
            if len(vector) != len(query_vector):
                continue
            ranked.append((section, _cosine_similarity(vector, query_vector)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked[:top_k]


def search_policy_sections(
    db: Session,
    query: str,
    policy_type: PolicyType | None,
    top_k: int,
    min_score: float,
    provider: PolicyEmbeddingProvider,
    expected_model: str,
    expected_dimensions: int,
) -> PolicySearchResponse:
    policies = _current_policies(db, policy_type)
    if not policies:
        return PolicySearchResponse(
            status=PolicyRetrievalStatus.NOT_APPLICABLE,
            items=[],
            provider=None,
            model=None,
            usage=PolicyEmbeddingUsage(input_tokens=0, total_tokens=0),
            latency_ms=0,
        )

    if any(
        not _is_current_index(policy, section, expected_model)
        for policy in policies
        for section in policy.sections
    ):
        return PolicySearchResponse(
            status=PolicyRetrievalStatus.NOT_INDEXED,
            items=[],
            provider=None,
            model=expected_model,
            usage=PolicyEmbeddingUsage(input_tokens=0, total_tokens=0),
            latency_ms=0,
        )

    try:
        result = provider.embed([query])
    except PolicyEmbeddingProviderError:
        logger.warning("policy_retrieval_failed policy_type=%s", policy_type)
        return PolicySearchResponse(
            status=PolicyRetrievalStatus.UNAVAILABLE,
            items=[],
            provider=None,
            model=expected_model,
            usage=PolicyEmbeddingUsage(input_tokens=0, total_tokens=0),
            latency_ms=0,
        )

    if (
        result.model != expected_model
        or len(result.vectors) != 1
        or len(result.vectors[0]) != expected_dimensions
    ):
        logger.warning("policy_retrieval_invalid_embedding model=%s", result.model)
        return PolicySearchResponse(
            status=PolicyRetrievalStatus.UNAVAILABLE,
            items=[],
            provider=result.provider,
            model=result.model,
            usage=PolicyEmbeddingUsage(
                input_tokens=result.usage.input_tokens,
                total_tokens=result.usage.total_tokens,
            ),
            latency_ms=result.latency_ms,
        )

    ranked = _rank_sections(db, policies, result.vectors[0], top_k)
    items = [_citation(section, score) for section, score in ranked if score >= min_score]
    logger.info(
        "policy_retrieval_completed policy_type=%s result_count=%s section_ids=%s "
        "model=%s latency_ms=%s input_tokens=%s",
        policy_type,
        len(items),
        [item.section_id for item in items],
        result.model,
        result.latency_ms,
        result.usage.input_tokens,
    )
    return PolicySearchResponse(
        status=PolicyRetrievalStatus.READY,
        items=items,
        provider=result.provider,
        model=result.model,
        usage=PolicyEmbeddingUsage(
            input_tokens=result.usage.input_tokens,
            total_tokens=result.usage.total_tokens,
        ),
        latency_ms=result.latency_ms,
    )

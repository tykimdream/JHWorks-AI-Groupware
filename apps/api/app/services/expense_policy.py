"""Read-only authoritative policy checks. No model, embeddings, or compliance score."""

import hashlib
import json

from sqlalchemy.orm import Session

from app.core.errors import ServiceUnavailableError
from app.models.enums import PolicyType
from app.models.policy import CompanyPolicy, PolicySection
from app.schemas.approval import ApprovalCreate
from app.schemas.expense_policy import ExpensePolicyValidation, ExpenseRuleCheck
from app.schemas.policy import PolicyCitation, PolicyRetrievalStatus, PolicySearchResponse
from app.services.policy_retrieval import current_policies


def _catalog(db: Session) -> list[CompanyPolicy]:
    # Same authenticated company-policy scope as existing retrieval, expense type only.
    return current_policies(db, PolicyType.EXPENSE)


def _fingerprint(policies: list[CompanyPolicy]) -> str:
    data = [
        {
            "id": p.policy_id,
            "version": p.version,
            "effective": p.effective_from.isoformat(),
            "title": p.title,
            "hash": p.content_hash,
            "sections": [
                {"id": s.section_id, "title": s.title, "content": s.content, "rule": s.rule_config}
                for s in sorted(p.sections, key=lambda s: s.section_id)
            ],
        }
        for p in sorted(policies, key=lambda p: p.policy_id)
    ]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def expense_policy_fingerprint(db: Session) -> str:
    return _fingerprint(_catalog(db))


def _citation(policy: CompanyPolicy, section: PolicySection) -> PolicyCitation:
    return PolicyCitation(
        citation_key=f"{policy.policy_id}:{policy.version}:{section.section_id}",
        policy_id=policy.policy_id,
        policy_title=policy.title,
        policy_type=policy.type,
        version=policy.version,
        section_id=section.section_id,
        section_title=section.title,
        excerpt=section.content[:1000],
        similarity_score=0.0,
    )


def validate_expense_policy(
    db: Session,
    preview: ApprovalCreate,
    retrieved: PolicySearchResponse,
) -> ExpensePolicyValidation:
    policies = _catalog(db)
    sources = {
        f"{p.policy_id}:{p.version}:{s.section_id}": (p, s) for p in policies for s in p.sections
    }
    for citation in retrieved.items:
        original = sources.get(citation.citation_key)
        if original is None or citation.model_dump(exclude={"similarity_score"}) != _citation(
            *original
        ).model_dump(exclude={"similarity_score"}):
            raise ServiceUnavailableError(
                "AI_POLICY_EVIDENCE_INVALID",
                "Policy evidence could not be verified. Prepare again.",
            )
    checks: list[ExpenseRuleCheck] = []
    citations: list[PolicyCitation] = []
    for key, (policy, section) in sources.items():
        citation = _citation(policy, section)
        citations.append(citation)
        rule = section.rule_config
        kind = rule.get("kind") if isinstance(rule, dict) else None
        threshold = rule.get("thresholdKrw") if isinstance(rule, dict) else None
        if kind == "RECEIPT_REQUIRED_MIN_TOTAL" and type(threshold) is int and threshold >= 0:
            required = preview.amount is not None and preview.amount >= threshold
            checks.append(
                ExpenseRuleCheck(
                    citation_key=key,
                    code="RECEIPT_REQUIRED_MIN_TOTAL",
                    outcome="ACTION_REQUIRED" if required else "NOT_APPLICABLE",
                    message=(
                        f"{threshold:,}원 이상 경비입니다. 원본 영수증을 별도로 확인해야 합니다. "
                        "참조 번호는 첨부·진위 확인을 대신하지 않습니다."
                        if required
                        else f"이 금액은 {threshold:,}원 영수증 기준의 적용 대상이 아닙니다."
                    ),
                )
            )
        else:
            checks.append(
                ExpenseRuleCheck(
                    citation_key=key,
                    code=str(kind or "NO_AUTOMATED_RULE"),
                    outcome="NOT_EVALUATED",
                    message="이 규정의 준수 여부는 자동 판정하지 않았습니다.",
                )
            )
    return ExpensePolicyValidation(
        status="CATALOG_CHECKED" if policies else "UNAVAILABLE",
        fingerprint=_fingerprint(policies),
        retrieval_checked=retrieved.status == PolicyRetrievalStatus.READY and bool(retrieved.items),
        citations=citations,
        checks=checks,
    )

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentEmployee, DbSession, PolicyEmbeddingProviderDependency
from app.core.config import get_settings
from app.models.enums import PolicyStatus
from app.models.policy import CompanyPolicy
from app.schemas.policy import PolicyRead, PolicySearchRequest, PolicySearchResponse
from app.services import policy_retrieval
from app.services.mappers import policy_read

router = APIRouter(prefix="/policies", tags=["정책"])


@router.get("", response_model=list[PolicyRead], summary="회사 정책 목록 조회")
def list_policies(db: DbSession, _: CurrentEmployee) -> list[PolicyRead]:
    """버전과 섹션으로 관리되는 가상 회사 정책을 조회합니다."""
    policies = db.scalars(
        select(CompanyPolicy)
        .options(selectinload(CompanyPolicy.sections))
        .where(CompanyPolicy.status == PolicyStatus.ACTIVE)
        .order_by(CompanyPolicy.title)
    )
    return [policy_read(policy) for policy in policies]


@router.post("/search", response_model=PolicySearchResponse, summary="관련 정책 검색")
def search_policies(
    payload: PolicySearchRequest,
    db: DbSession,
    _: CurrentEmployee,
    provider: PolicyEmbeddingProviderDependency,
) -> PolicySearchResponse:
    """
    업무 요청과 관련된 정책 섹션을 검색하고 원문·버전·섹션 식별자를
    반환합니다.
    """
    settings = get_settings()
    return policy_retrieval.search_policy_sections(
        db=db,
        query=payload.query.strip(),
        policy_type=payload.policy_type,
        top_k=payload.top_k or settings.policy_retrieval_top_k,
        min_score=settings.policy_retrieval_min_score,
        provider=provider,
        expected_model=settings.policy_embedding_model,
        expected_dimensions=settings.policy_embedding_dimensions,
    )

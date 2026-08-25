from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentEmployee, DbSession
from app.models.enums import PolicyStatus
from app.models.policy import CompanyPolicy
from app.schemas.policy import PolicyRead
from app.services.mappers import policy_read

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("", response_model=list[PolicyRead])
def list_policies(db: DbSession, _: CurrentEmployee) -> list[PolicyRead]:
    policies = db.scalars(
        select(CompanyPolicy)
        .options(selectinload(CompanyPolicy.sections))
        .where(CompanyPolicy.status == PolicyStatus.ACTIVE)
        .order_by(CompanyPolicy.title)
    )
    return [policy_read(policy) for policy in policies]

from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.ai.approval_draft import ApprovalDraftProvider, UnavailableApprovalDraftProvider
from app.ai.approval_review import ApprovalReviewProvider, UnavailableApprovalReviewProvider
from app.ai.openai_approval_draft import OpenAIApprovalDraftProvider
from app.ai.openai_approval_review import OpenAIApprovalReviewProvider
from app.ai.openai_policy_embedding import OpenAIPolicyEmbeddingProvider
from app.ai.policy_embedding import PolicyEmbeddingProvider, UnavailablePolicyEmbeddingProvider
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AuthenticationError
from app.core.security import decode_session_token
from app.models.employee import Employee

DbSession = Annotated[Session, Depends(get_db)]


def get_current_employee(
    db: DbSession,
    session_token: Annotated[str | None, Cookie(alias=get_settings().session_cookie_name)] = None,
) -> Employee:
    if session_token is None:
        raise AuthenticationError()

    employee_id = decode_session_token(session_token)
    employee = db.scalar(
        select(Employee)
        .options(joinedload(Employee.department), joinedload(Employee.manager))
        .where(Employee.id == employee_id)
    )
    if employee is None or not employee.is_active:
        raise AuthenticationError("The employee account is unavailable")
    return employee


CurrentEmployee = Annotated[Employee, Depends(get_current_employee)]


def get_approval_review_provider() -> ApprovalReviewProvider:
    settings = get_settings()
    api_key = settings.openai_api_key
    secret = api_key.get_secret_value() if api_key else ""
    if not secret:
        return UnavailableApprovalReviewProvider()
    return OpenAIApprovalReviewProvider(
        api_key=secret,
        model=settings.openai_model,
        timeout_seconds=settings.ai_review_timeout_seconds,
    )


AIReviewProvider = Annotated[ApprovalReviewProvider, Depends(get_approval_review_provider)]


def get_approval_draft_provider() -> ApprovalDraftProvider:
    settings = get_settings()
    api_key = settings.openai_api_key
    secret = api_key.get_secret_value() if api_key else ""
    if not secret:
        return UnavailableApprovalDraftProvider()
    return OpenAIApprovalDraftProvider(
        api_key=secret,
        model=settings.openai_model,
        timeout_seconds=settings.ai_review_timeout_seconds,
    )


AIApprovalDraftProvider = Annotated[ApprovalDraftProvider, Depends(get_approval_draft_provider)]


def get_policy_embedding_provider() -> PolicyEmbeddingProvider:
    settings = get_settings()
    api_key = settings.openai_api_key
    secret = api_key.get_secret_value() if api_key else ""
    if not secret:
        return UnavailablePolicyEmbeddingProvider()
    return OpenAIPolicyEmbeddingProvider(
        api_key=secret,
        model=settings.policy_embedding_model,
        dimensions=settings.policy_embedding_dimensions,
        timeout_seconds=settings.ai_review_timeout_seconds,
    )


PolicyEmbeddingProviderDependency = Annotated[
    PolicyEmbeddingProvider, Depends(get_policy_embedding_provider)
]

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.ai.approval_draft import ApprovalDraftProvider, UnavailableApprovalDraftProvider
from app.ai.approval_review import ApprovalReviewProvider, UnavailableApprovalReviewProvider
from app.ai.budgeted_expense_draft import BudgetedExpenseDraftProvider
from app.ai.expense_pricing import MODEL as PUBLIC_EXPENSE_MODEL
from app.ai.leave_assistant import LeaveAssistantProvider, UnavailableLeaveAssistantProvider
from app.ai.openai_approval_draft import OpenAIApprovalDraftProvider
from app.ai.openai_approval_review import OpenAIApprovalReviewProvider
from app.ai.openai_leave_assistant import OpenAILeaveAssistantProvider
from app.ai.openai_policy_embedding import OpenAIPolicyEmbeddingProvider
from app.ai.openai_work_assistant import OpenAIWorkAssistantProvider
from app.ai.policy_embedding import PolicyEmbeddingProvider, UnavailablePolicyEmbeddingProvider
from app.ai.work_assistant import UnavailableWorkAssistantProvider, WorkAssistantProvider
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AuthenticationError
from app.core.security import decode_session_token
from app.models.employee import Employee
from app.schemas.demo import AICapabilities
from app.services.demo_workspace import require_demo_workspace

DbSession = Annotated[Session, Depends(get_db)]
session_cookie = APIKeyCookie(
    name=get_settings().session_cookie_name,
    scheme_name="SessionCookie",
    description="Login/demo start sets this HttpOnly cookie; existing authorization checks apply.",
    auto_error=False,
)


def _session_employee(db: Session, session_token: str | None) -> Employee:
    if session_token is None:
        raise AuthenticationError()

    employee_id = decode_session_token(session_token)
    employee = db.scalar(
        select(Employee)
        .options(joinedload(Employee.department), joinedload(Employee.manager))
        .where(Employee.id == employee_id)
    )
    if (
        employee is None
        or not employee.is_active
        or (get_settings().public_demo_enabled and employee.demo_workspace_id is None)
    ):
        raise AuthenticationError("The employee account is unavailable")
    return employee


def get_current_employee(
    request: Request,
    db: DbSession,
    session_token: Annotated[str | None, Depends(session_cookie)] = None,
) -> Employee:
    employee = _session_employee(db, session_token)
    require_demo_workspace(db, employee, write=request.method not in {"GET", "HEAD", "OPTIONS"})
    return employee


def get_feedback_employee(
    db: DbSession,
    session_token: Annotated[str | None, Depends(session_cookie)] = None,
) -> Employee:
    employee = _session_employee(db, session_token)
    if employee.demo_workspace_id is None:
        raise AuthenticationError()
    require_demo_workspace(db, employee, admit=False)
    return employee


FeedbackEmployee = Annotated[Employee, Depends(get_feedback_employee)]
CurrentEmployee = Annotated[Employee, Depends(get_current_employee)]


def get_approval_review_provider() -> ApprovalReviewProvider:
    settings = get_settings()
    api_key = settings.openai_api_key
    secret = api_key.get_secret_value() if api_key else ""
    if not settings.allows_ai("approval_review") or not secret:
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
    # Unscoped factories/evals cannot bypass the public workspace budget.
    if settings.public_demo_enabled or not settings.allows_ai("approval_draft") or not secret:
        return UnavailableApprovalDraftProvider()
    return OpenAIApprovalDraftProvider(
        api_key=secret,
        model=settings.openai_model,
        timeout_seconds=settings.ai_review_timeout_seconds,
    )


def get_scoped_approval_draft_provider(
    db: DbSession,
    actor: CurrentEmployee,
    provider: Annotated[ApprovalDraftProvider, Depends(get_approval_draft_provider)],
) -> ApprovalDraftProvider:
    settings = get_settings()
    if not settings.public_demo_enabled:
        return provider
    budget = settings.public_expense_ai_budget
    if not settings.allows_ai("approval_draft") or budget is None or not actor.demo_workspace_id:
        return UnavailableApprovalDraftProvider()
    # CurrentEmployee has already validated persisted workspace membership and expiry.
    api_key = settings.openai_api_key
    if api_key is None:
        return UnavailableApprovalDraftProvider()
    secret = api_key.get_secret_value()
    actor_id, workspace_id = actor.id, actor.demo_workspace_id

    def recheck_authorization(budget_db: Session) -> None:
        employee = budget_db.get(Employee, actor_id)
        if employee is None or not employee.is_active or employee.demo_workspace_id != workspace_id:
            raise AuthenticationError("The demo workspace membership changed")
        require_demo_workspace(budget_db, employee, admit=False)

    return BudgetedExpenseDraftProvider(
        workspace_id=actor.demo_workspace_id,
        factory=sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False),
        provider_factory=lambda: OpenAIApprovalDraftProvider(
            api_key=secret,
            model=PUBLIC_EXPENSE_MODEL,
            timeout_seconds=20.0,
            max_retries=0,
            standard_tier=True,
        ),
        limits=budget,
        check_authorization=recheck_authorization,
    )


AIApprovalDraftProvider = Annotated[
    ApprovalDraftProvider, Depends(get_scoped_approval_draft_provider)
]


def get_leave_assistant_provider() -> LeaveAssistantProvider:
    settings = get_settings()
    api_key = settings.openai_api_key
    secret = api_key.get_secret_value() if api_key else ""
    if not settings.allows_ai("leave_assistant") or not secret:
        return UnavailableLeaveAssistantProvider()
    return OpenAILeaveAssistantProvider(
        api_key=secret,
        model=settings.openai_model,
        timeout_seconds=settings.ai_review_timeout_seconds,
    )


LeaveAssistantProviderDependency = Annotated[
    LeaveAssistantProvider, Depends(get_leave_assistant_provider)
]


def get_work_assistant_provider() -> WorkAssistantProvider:
    settings = get_settings()
    api_key = settings.openai_api_key
    secret = api_key.get_secret_value() if api_key else ""
    if not settings.allows_ai("work_assistant") or not secret:
        return UnavailableWorkAssistantProvider()
    return OpenAIWorkAssistantProvider(
        api_key=secret,
        model=settings.openai_model,
        timeout_seconds=settings.ai_review_timeout_seconds,
    )


WorkAssistantProviderDependency = Annotated[
    WorkAssistantProvider, Depends(get_work_assistant_provider)
]


def get_policy_embedding_provider() -> PolicyEmbeddingProvider:
    settings = get_settings()
    api_key = settings.openai_api_key
    secret = api_key.get_secret_value() if api_key else ""
    if not settings.allows_ai("policy_embedding") or not secret:
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


def get_ai_capabilities() -> AICapabilities:
    settings = get_settings()
    return AICapabilities(
        approval_draft=settings.allows_ai("approval_draft"),
        approval_review=settings.allows_ai("approval_review"),
        leave_assistant=settings.allows_ai("leave_assistant"),
        work_assistant=settings.allows_ai("work_assistant"),
        policy_embedding=settings.allows_ai("policy_embedding"),
    )

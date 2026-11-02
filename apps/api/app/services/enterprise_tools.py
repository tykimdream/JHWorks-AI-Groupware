from datetime import date
from typing import Any

from pydantic import Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.policy_embedding import PolicyEmbeddingProvider
from app.ai.work_assistant import ToolExecutionError
from app.core.config import get_settings
from app.core.schema import ApiSchema
from app.models.approval import Approval
from app.models.attendance import LeaveAccount
from app.models.employee import Employee
from app.models.enums import ApprovalStatus, PolicyType
from app.services import approval as approval_service
from app.services import policy_retrieval


class NoArguments(ApiSchema):
    pass


class ListMyApprovalsArguments(ApiSchema):
    status: ApprovalStatus | None
    limit: int = Field(ge=1, le=10)


class SearchCompanyPolicyArguments(ApiSchema):
    query: str = Field(min_length=2, max_length=1000)
    policy_type: PolicyType | None
    top_k: int = Field(ge=1, le=4)


class ReadOnlyEnterpriseToolExecutor:
    def __init__(
        self,
        db: Session,
        actor: Employee,
        embedding_provider: PolicyEmbeddingProvider,
    ) -> None:
        self._db = db
        self._actor = actor
        self._embedding_provider = embedding_provider

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "get_current_employee":
                NoArguments.model_validate(arguments)
                return self._current_employee()
            if name == "get_my_manager":
                NoArguments.model_validate(arguments)
                return self._manager()
            if name == "list_my_approvals":
                approval_arguments = ListMyApprovalsArguments.model_validate(arguments)
                return self._approvals(approval_arguments)
            if name == "search_company_policy":
                policy_arguments = SearchCompanyPolicyArguments.model_validate(arguments)
                return self._policy_search(policy_arguments)
        except ValidationError as exc:
            raise ToolExecutionError(f"Invalid arguments for {name}") from exc
        raise ToolExecutionError(f"Unknown enterprise tool: {name}")

    def _current_employee(self) -> dict[str, Any]:
        leave_account = self._db.scalar(
            select(LeaveAccount).where(
                LeaveAccount.employee_id == self._actor.id,
                LeaveAccount.year == date.today().year,
            )
        )
        return {
            "employee": {
                "id": self._actor.id,
                "name": self._actor.name,
                "email": self._actor.email,
                "department": self._actor.department.name,
                "position": self._actor.position,
                "role": self._actor.role.value,
                "leaveBalanceDays": float(
                    leave_account.available_days
                    if leave_account is not None
                    else self._actor.leave_balance
                ),
            }
        }

    def _manager(self) -> dict[str, Any]:
        manager = self._actor.manager
        if manager is None or not manager.is_active:
            return {"manager": None}
        return {
            "manager": {
                "id": manager.id,
                "name": manager.name,
                "email": manager.email,
                "department": manager.department.name,
                "position": manager.position,
            }
        }

    def _approvals(self, arguments: ListMyApprovalsArguments) -> dict[str, Any]:
        # Reuse the same actor/workspace visibility predicate as the full list.
        visible = approval_service.visible_approval_query(self._actor).where(
            Approval.author_id == self._actor.id
        )
        if arguments.status is not None:
            visible = visible.where(Approval.status == arguments.status)
        scoped = visible.subquery()
        total = self._db.scalar(select(func.count()).select_from(scoped)) or 0
        rows = self._db.execute(
            select(scoped.c.id, scoped.c.type, scoped.c.title, scoped.c.status,
                   scoped.c.amount, scoped.c.version, scoped.c.updated_at)
            .order_by(scoped.c.updated_at.desc(), scoped.c.id.desc())
            .limit(arguments.limit)
        ).all()
        return {
            "total": total,
            "items": [
                {
                    "id": item.id,
                    "type": item.type.value,
                    "title": item.title,
                    "status": item.status.value,
                    "amount": item.amount,
                    "version": item.version,
                    "updatedAt": item.updated_at.isoformat(),
                }
                for item in rows
            ],
        }

    def _policy_search(self, arguments: SearchCompanyPolicyArguments) -> dict[str, Any]:
        settings = get_settings()
        result = policy_retrieval.search_policy_sections(
            db=self._db,
            query=arguments.query,
            policy_type=arguments.policy_type,
            top_k=arguments.top_k,
            min_score=settings.policy_retrieval_min_score,
            provider=self._embedding_provider,
            expected_model=settings.policy_embedding_model,
            expected_dimensions=settings.policy_embedding_dimensions,
        )
        return result.model_dump(mode="json", by_alias=True)

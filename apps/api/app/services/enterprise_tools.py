from typing import Any

from pydantic import Field, ValidationError
from sqlalchemy.orm import Session

from app.ai.policy_embedding import PolicyEmbeddingProvider
from app.ai.work_assistant import ToolExecutionError
from app.core.config import get_settings
from app.core.schema import ApiSchema
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
        return {
            "employee": {
                "id": self._actor.id,
                "name": self._actor.name,
                "email": self._actor.email,
                "department": self._actor.department.name,
                "position": self._actor.position,
                "role": self._actor.role.value,
                "leaveBalanceDays": float(self._actor.leave_balance),
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
        approvals = approval_service.list_approvals(self._db, self._actor, "mine")
        if arguments.status is not None:
            approvals = [item for item in approvals if item.status == arguments.status]
        limited = approvals[: arguments.limit]
        return {
            "total": len(approvals),
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
                for item in limited
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

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.ai.openai_policy_embedding import OpenAIPolicyEmbeddingProvider
from app.ai.work_assistant import WorkAssistantProviderError
from app.api.dependencies import get_work_assistant_provider
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.employee import Employee
from app.services.enterprise_tools import ReadOnlyEnterpriseToolExecutor
from app.services.policy_retrieval import index_active_policy_sections

DATASET_PATH = Path(__file__).parents[2] / "evals" / "work_assistant_cases.json"


class WorkAssistantEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    message: str
    expected_tool_names: list[str] = Field(min_length=1)
    expected_arguments: dict[str, dict[str, Any]] = Field(default_factory=dict)
    expected_citation_keys: list[str] = Field(default_factory=list)


def load_cases() -> list[WorkAssistantEvalCase]:
    raw = json.loads(DATASET_PATH.read_text())
    return [WorkAssistantEvalCase.model_validate(item) for item in raw]


def main() -> int:
    settings = get_settings()
    api_key = settings.openai_api_key
    secret = api_key.get_secret_value() if api_key else ""
    if not secret:
        print("Work assistant evaluation requires JHWORKS_OPENAI_API_KEY.")
        return 2

    provider = get_work_assistant_provider()
    embedding_provider = OpenAIPolicyEmbeddingProvider(
        api_key=secret,
        model=settings.policy_embedding_model,
        dimensions=settings.policy_embedding_dimensions,
        timeout_seconds=settings.ai_review_timeout_seconds,
    )
    safety_identifier = hashlib.sha256(b"jhworks-work-assistant-eval").hexdigest()
    outcomes: list[dict[str, object]] = []

    with SessionLocal() as db:
        index_active_policy_sections(
            db,
            embedding_provider,
            settings.policy_embedding_model,
            settings.policy_embedding_dimensions,
        )
        actor = db.scalar(
            select(Employee)
            .options(joinedload(Employee.department), joinedload(Employee.manager))
            .where(Employee.email == "seojin.yoon@jhworks.test")
        )
        if actor is None:
            raise SystemExit("Synthetic evaluation employee is missing")
        executor = ReadOnlyEnterpriseToolExecutor(db, actor, embedding_provider)

        for case in load_cases():
            try:
                result = provider.answer(case.message, executor, safety_identifier)
            except WorkAssistantProviderError:
                print("Work assistant provider failed. No application data was changed.")
                return 2

            names = [execution.name for execution in result.executions]
            executions_by_name = {execution.name: execution for execution in result.executions}
            tool_match = all(name in names for name in case.expected_tool_names)
            argument_match = all(
                name in executions_by_name
                and all(
                    executions_by_name[name].arguments.get(key) == value
                    for key, value in expected.items()
                )
                for name, expected in case.expected_arguments.items()
            )
            citations = {
                str(item.get("citationKey"))
                for execution in result.executions
                if execution.name == "search_company_policy"
                for item in execution.result.get("items", [])
                if isinstance(item, dict)
            }
            citation_match = all(
                key in citations for key in case.expected_citation_keys
            )
            passed = tool_match and argument_match and citation_match
            outcomes.append(
                {
                    "id": case.id,
                    "passed": passed,
                    "expectedTools": case.expected_tool_names,
                    "actualTools": names,
                    "arguments": {
                        execution.name: execution.arguments for execution in result.executions
                    },
                    "citations": sorted(citations),
                    "roundCount": result.round_count,
                    "latencyMs": result.latency_ms,
                    "totalTokens": result.usage.total_tokens,
                    "model": result.model,
                }
            )

    passed_count = sum(bool(outcome["passed"]) for outcome in outcomes)
    print(
        json.dumps(
            {
                "summary": {"passed": passed_count, "total": len(outcomes)},
                "results": outcomes,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if passed_count == len(outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())

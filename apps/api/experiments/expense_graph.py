"""Local-only LangGraph experiment around the existing preview service.

No API endpoint, production checkpoint, budget guard, or write/confirmation tool.
Use only synthetic data and fake providers in the comparison tests.
"""

from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.approval_draft import ApprovalDraftProvider
from app.ai.policy_embedding import PolicyEmbeddingProvider
from app.models.employee import Employee
from app.schemas.approval_draft_ai import ApprovalDraftPrepareRequest
from app.services.approval_draft import prepare_approval_draft


class ExpenseState(TypedDict, total=False):
    request: str
    answers: list[str]
    result: dict[str, Any]
    cancelled: bool
    answer_limit_reached: bool


def build_graph(
    db: Session,
    actor: Employee,
    provider: ApprovalDraftProvider,
    embedding_provider: PolicyEmbeddingProvider,
    checkpointer: BaseCheckpointSaver,
):
    """Bind local dependencies outside checkpoint state and compile a preview-only graph."""

    def prepare(state: ExpenseState) -> dict[str, Any]:
        payload = ApprovalDraftPrepareRequest(request=state["request"], answers=state["answers"])
        result = prepare_approval_draft(
            db, actor, payload, provider, embedding_provider, issue_confirmation=False
        )
        return {"result": result.model_dump(mode="json")}

    def ask(state: ExpenseState) -> dict[str, Any]:
        # The node replays on resume. Never call the provider or write here.
        if len(state["answers"]) >= 8:
            return {"answer_limit_reached": True}
        error = None
        while True:
            reply = interrupt({"questions": state["result"]["questions"], "error": error})
            if isinstance(reply, dict) and reply.get("cancel") is True:
                return {"cancelled": True}
            if not isinstance(reply, str) or not reply.strip():
                error = "답변을 입력해 주세요."
                continue
            answers = [*state["answers"], reply.strip()]
            try:
                ApprovalDraftPrepareRequest(request=state["request"], answers=answers)
            except ValidationError:
                error = "답변은 2,000자 이하여야 합니다."
                continue
            return {"answers": answers}

    graph = StateGraph(ExpenseState)
    graph.add_node("prepare", prepare)
    graph.add_node("ask", ask)
    graph.add_edge(START, "prepare")
    graph.add_conditional_edges(
        "prepare",
        lambda state: "ask" if state["result"]["status"] == "NEEDS_INPUT" else END,
        {"ask": "ask", END: END},
    )
    graph.add_conditional_edges(
        "ask",
        lambda state: (
            END if state.get("cancelled") or state.get("answer_limit_reached") else "prepare"
        ),
        {"prepare": "prepare", END: END},
    )
    return graph.compile(checkpointer=checkpointer)

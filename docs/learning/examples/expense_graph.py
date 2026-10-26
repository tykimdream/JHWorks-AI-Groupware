# /// script
# requires-python = ">=3.11"
# dependencies = ["langgraph==1.2.17", "langgraph-checkpoint-sqlite==3.1.2"]
# ///
"""Synthetic learning lab. No model, business writes, auth, or API integration."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict

# Never enable external tracing through inherited developer settings in this lab.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402
from langgraph.types import Command, interrupt  # noqa: E402


class ExpenseState(TypedDict, total=False):
    amount: int
    merchant: str
    status: str
    preview: str


def complete_fields(state: ExpenseState) -> dict:
    # Only pure validation precedes interrupt: this node runs again on resume.
    amount = state.get("amount")
    if type(amount) is not int or amount <= 0:
        raise ValueError("amount must be a positive integer")
    if state.get("merchant", "").strip():
        return {"status": "ready"}
    answer = interrupt({"missing": ["merchant"], "question": "사용처를 입력해 주세요."})
    if not isinstance(answer, dict):
        raise ValueError("resume must be an object")
    if answer.get("cancel") is True:
        return {"status": "cancelled"}
    merchant = answer.get("merchant")
    if not isinstance(merchant, str) or not merchant.strip() or len(merchant) > 80:
        raise ValueError("merchant must be a non-empty string of at most 80 characters")
    return {"merchant": merchant.strip(), "status": "ready"}


def preview(state: ExpenseState) -> dict:
    return {
        "status": "preview",
        "preview": f"{state['merchant']} · {state['amount']:,}원 (학습용 미리보기)",
    }


def build(checkpointer):
    builder = StateGraph(ExpenseState)
    builder.add_node("complete_fields", complete_fields)
    builder.add_node("preview", preview)
    builder.add_edge(START, "complete_fields")
    builder.add_conditional_edges(
        "complete_fields",
        lambda state: "cancelled" if state["status"] == "cancelled" else "ready",
        {"cancelled": END, "ready": "preview"},
    )
    builder.add_edge("preview", END)
    return builder.compile(checkpointer=checkpointer)


def main() -> None:
    with TemporaryDirectory(prefix="jhworks-graph-learning-") as directory:
        database = str(Path(directory) / "checkpoint.sqlite")
        config = {"configurable": {"thread_id": "synthetic-expense-1"}}
        with SqliteSaver.from_conn_string(database) as saver:
            paused = build(saver).invoke({"amount": 170000}, config)
            assert paused["__interrupt__"]
            assert "preview" not in paused
        # Close the first connection and compile a new graph; not a process restart.
        with SqliteSaver.from_conn_string(database) as saver:
            graph = build(saver)
            resumed = graph.invoke(Command(resume={"merchant": "합성 전시장"}), config)
            assert resumed["status"] == "preview"
            assert "170,000원" in resumed["preview"]
            assert not resumed.get("__interrupt__")

            cancel_config = {"configurable": {"thread_id": "synthetic-cancel"}}
            graph.invoke({"amount": 170000}, cancel_config)
            cancelled = graph.invoke(Command(resume={"cancel": True}), cancel_config)
            assert cancelled["status"] == "cancelled"
            assert "preview" not in cancelled

            invalid_config = {"configurable": {"thread_id": "synthetic-invalid"}}
            graph.invoke({"amount": 170000}, invalid_config)
            try:
                graph.invoke(Command(resume={"merchant": " "}), invalid_config)
            except ValueError:
                assert "preview" not in graph.get_state(invalid_config).values
            else:
                raise AssertionError("Invalid merchant was accepted")
    print("PASS: pause, reconnect/resume, cancel, invalid input; model calls=0; business writes=0")


if __name__ == "__main__":
    main()

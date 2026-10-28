"""Opt-in local comparison; no production graph dependency or real model calls."""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

pytest_plugins = ["tests.conftest"]

pytest.importorskip("langgraph")
pytest.importorskip("langgraph.checkpoint.sqlite")

from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402
from langgraph.types import Command  # noqa: E402

from app.ai.approval_draft import ApprovalDraftCandidate, DraftIntent  # noqa: E402
from app.core.errors import ServiceUnavailableError  # noqa: E402
from app.models.approval import Approval  # noqa: E402
from app.models.employee import Employee  # noqa: E402
from app.models.enums import ExpenseCategory  # noqa: E402
from app.schemas.approval_draft_ai import ApprovalDraftPrepareRequest  # noqa: E402
from app.services.approval_draft import prepare_approval_draft  # noqa: E402
from experiments.expense_graph import build_graph  # noqa: E402
from tests.conftest import FakeApprovalDraftProvider, FakePolicyEmbeddingProvider  # noqa: E402


@pytest.fixture(autouse=True)
def disable_tracing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


REQUEST = "코엑스 전시회 출장 교통비 38,000원 정산해줘."
ANSWER = "지출일: 2026-01-08, 사용처: 코레일, 분류: 교통비, 목적: 코엑스 전시회 출장"


def candidate(complete: bool) -> ApprovalDraftCandidate:
    return ApprovalDraftCandidate(
        intent=DraftIntent.EXPENSE,
        amount=38000,
        expense_date=date(2026, 1, 8) if complete else None,
        merchant="코레일" if complete else None,
        expense_category=ExpenseCategory.TRANSPORTATION,
        expense_purpose="코엑스 전시회 출장",
    )


def contract(result):
    return {
        key: result[key]
        for key in (
            "status",
            "missing_fields",
            "questions",
            "candidate",
            "preview",
            "grounding",
            "policy_validation",
            "policy_context",
        )
    }


def test_same_service_contract_pause_reconnect_resume_and_cancel(
    tmp_path,
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
    fake_embedding_provider: FakePolicyEmbeddingProvider,
):
    with session_factory() as db:
        actor = db.scalar(select(Employee).where(Employee.email == "seojin.yoon@jhworks.test"))
        assert actor is not None
        before = db.scalar(select(func.count()).select_from(Approval))
        fake_draft_provider.candidate = candidate(False)
        direct_first = prepare_approval_draft(
            db,
            actor,
            ApprovalDraftPrepareRequest(request=REQUEST),
            fake_draft_provider,
            fake_embedding_provider,
            issue_confirmation=False,
        ).model_dump(mode="json")
        fake_draft_provider.candidate = candidate(True)
        direct_final = prepare_approval_draft(
            db,
            actor,
            ApprovalDraftPrepareRequest(request=REQUEST, answers=[ANSWER]),
            fake_draft_provider,
            fake_embedding_provider,
            issue_confirmation=False,
        ).model_dump(mode="json")
        assert direct_first["status"] == "NEEDS_INPUT"
        assert direct_final["status"] == "PREVIEW"
        direct_calls = len(fake_draft_provider.inputs)
        fake_draft_provider.inputs.clear()
        fake_draft_provider.candidate = candidate(False)
        config = {"configurable": {"thread_id": "synthetic-expense"}}
        db_path = str(tmp_path / "checkpoints.sqlite")
        with SqliteSaver.from_conn_string(db_path) as saver:
            graph = build_graph(db, actor, fake_draft_provider, fake_embedding_provider, saver)
            first = graph.invoke({"request": REQUEST, "answers": []}, config)
            assert first["__interrupt__"]
            assert contract(first["result"]) == contract(direct_first)
        fake_draft_provider.candidate = candidate(True)
        with SqliteSaver.from_conn_string(db_path) as saver:
            graph = build_graph(db, actor, fake_draft_provider, fake_embedding_provider, saver)
            final = graph.invoke(Command(resume=ANSWER), config)
            assert contract(final["result"]) == contract(direct_final)
            assert final["result"]["confirmation_token"] is None
            assert len(fake_draft_provider.inputs) == direct_calls == 2
            fake_draft_provider.candidate = candidate(False)
            cancel_config = {"configurable": {"thread_id": "synthetic-cancel"}}
            graph.invoke({"request": REQUEST, "answers": []}, cancel_config)
            calls_before_cancel = len(fake_draft_provider.inputs)
            cancelled = graph.invoke(Command(resume={"cancel": True}), cancel_config)
            assert cancelled["cancelled"] is True
            assert len(fake_draft_provider.inputs) == calls_before_cancel
        assert db.scalar(select(func.count()).select_from(Approval)) == before


def test_provider_failure_can_resume_without_approval_write(
    tmp_path,
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
    fake_embedding_provider: FakePolicyEmbeddingProvider,
):
    with (
        session_factory() as db,
        SqliteSaver.from_conn_string(str(tmp_path / "failure.sqlite")) as saver,
    ):
        actor = db.scalar(select(Employee).where(Employee.email == "seojin.yoon@jhworks.test"))
        assert actor is not None
        before = db.scalar(select(func.count()).select_from(Approval))
        fake_draft_provider.candidate = candidate(False)
        fake_draft_provider.should_fail = True
        graph = build_graph(db, actor, fake_draft_provider, fake_embedding_provider, saver)
        config = {"configurable": {"thread_id": "synthetic-failure"}}
        with pytest.raises(ServiceUnavailableError):
            graph.invoke({"request": REQUEST, "answers": []}, config)
        fake_draft_provider.should_fail = False
        resumed = graph.invoke(None, config)
        assert resumed["result"]["status"] == "NEEDS_INPUT"
        assert resumed["__interrupt__"]
        assert db.scalar(select(func.count()).select_from(Approval)) == before


def test_empty_answer_is_rejected_and_corrected_without_an_extra_model_call(
    tmp_path,
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
    fake_embedding_provider: FakePolicyEmbeddingProvider,
):
    with (
        session_factory() as db,
        SqliteSaver.from_conn_string(str(tmp_path / "invalid.sqlite")) as saver,
    ):
        actor = db.scalar(select(Employee).where(Employee.email == "seojin.yoon@jhworks.test"))
        assert actor is not None
        fake_draft_provider.candidate = candidate(False)
        graph = build_graph(db, actor, fake_draft_provider, fake_embedding_provider, saver)
        config = {"configurable": {"thread_id": "synthetic-invalid"}}
        graph.invoke({"request": REQUEST, "answers": []}, config)
        invalid = graph.invoke(Command(resume="   "), config)
        assert invalid["__interrupt__"][0].value["error"] == "답변을 입력해 주세요."
        assert len(fake_draft_provider.inputs) == 1
        fake_draft_provider.candidate = candidate(True)
        final = graph.invoke(Command(resume=ANSWER), config)
        assert final["result"]["status"] == "PREVIEW"
        assert len(fake_draft_provider.inputs) == 2


def test_failure_after_answer_retries_prepare_without_asking_again(
    tmp_path,
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
    fake_embedding_provider: FakePolicyEmbeddingProvider,
):
    with (
        session_factory() as db,
        SqliteSaver.from_conn_string(str(tmp_path / "resume.sqlite")) as saver,
    ):
        actor = db.scalar(select(Employee).where(Employee.email == "seojin.yoon@jhworks.test"))
        assert actor is not None
        graph = build_graph(db, actor, fake_draft_provider, fake_embedding_provider, saver)
        config = {"configurable": {"thread_id": "synthetic-retry-after-answer"}}
        fake_draft_provider.candidate = candidate(False)
        graph.invoke({"request": REQUEST, "answers": []}, config)
        fake_draft_provider.candidate = candidate(True)
        fake_draft_provider.should_fail = True
        with pytest.raises(ServiceUnavailableError):
            graph.invoke(Command(resume=ANSWER), config)
        fake_draft_provider.should_fail = False
        final = graph.invoke(None, config)
        assert final["result"]["status"] == "PREVIEW"
        assert final["answers"] == [ANSWER]
        assert len(fake_draft_provider.inputs) == 2
        assert fake_draft_provider.inputs[-1].answers == [ANSWER]


def test_stops_at_the_existing_eight_answer_limit(
    tmp_path,
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
    fake_embedding_provider: FakePolicyEmbeddingProvider,
):
    with (
        session_factory() as db,
        SqliteSaver.from_conn_string(str(tmp_path / "limit.sqlite")) as saver,
    ):
        actor = db.scalar(select(Employee).where(Employee.email == "seojin.yoon@jhworks.test"))
        assert actor is not None
        fake_draft_provider.candidate = candidate(False)
        graph = build_graph(db, actor, fake_draft_provider, fake_embedding_provider, saver)
        config = {"configurable": {"thread_id": "synthetic-limit"}}
        result = graph.invoke({"request": REQUEST, "answers": ["확인 중"] * 8}, config)
        assert result["answer_limit_reached"] is True
        assert not result.get("__interrupt__")
        assert len(fake_draft_provider.inputs) == 1

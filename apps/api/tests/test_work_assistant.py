from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.work_assistant import TOOL_DEFINITIONS, ToolExecutionError
from app.evals.work_assistant import load_cases
from app.models.approval import Approval
from app.models.employee import Employee
from app.services.enterprise_tools import ReadOnlyEnterpriseToolExecutor
from app.services.policy_retrieval import index_active_policy_sections
from tests.conftest import FakePolicyEmbeddingProvider, FakeWorkAssistantProvider


def approval_count(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as db:
        return db.scalar(select(func.count()).select_from(Approval)) or 0


def test_current_employee_tool_returns_exact_leave_balance_without_writes(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_work_assistant_provider: FakeWorkAssistantProvider,
) -> None:
    fake_work_assistant_provider.answer_text = "윤서진님의 남은 연차는 9.5일입니다."
    fake_work_assistant_provider.planned_calls = [("get_current_employee", {})]
    before = approval_count(session_factory)
    login(client, "seojin.yoon@jhworks.test")

    response = client.post(
        "/api/v1/work-assistant/query",
        json={"message": "내 남은 연차가 며칠이야?"},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["toolExecutions"][0]["name"] == "get_current_employee"
    employee = result["toolExecutions"][0]["result"]["employee"]
    assert employee["email"] == "seojin.yoon@jhworks.test"
    assert employee["leaveBalanceDays"] == 9.5
    assert approval_count(session_factory) == before


def test_manager_tool_is_scoped_to_the_signed_in_employee(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_work_assistant_provider: FakeWorkAssistantProvider,
) -> None:
    fake_work_assistant_provider.planned_calls = [("get_my_manager", {})]
    login(client, "seojin.yoon@jhworks.test")

    response = client.post(
        "/api/v1/work-assistant/query",
        json={"message": "내 직속 관리자가 누구야?"},
    )

    assert response.status_code == 200, response.text
    manager = response.json()["toolExecutions"][0]["result"]["manager"]
    assert manager["email"] == "doyun.choi@jhworks.test"


def test_approval_tool_returns_only_the_actor_owned_documents(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_work_assistant_provider: FakeWorkAssistantProvider,
) -> None:
    fake_work_assistant_provider.planned_calls = [
        ("list_my_approvals", {"status": None, "limit": 10})
    ]
    login(client, "doyun.choi@jhworks.test")
    other = client.post(
        "/api/v1/approvals",
        json={
            "type": "GENERAL",
            "title": "관리자 소유 문서",
            "content": "관리자 본인의 문서입니다.",
            "amount": None,
            "details": {"kind": "GENERAL"},
            "attachmentMetadata": [],
        },
    )
    assert other.status_code == 201
    login(client, "seojin.yoon@jhworks.test")

    response = client.post(
        "/api/v1/work-assistant/query",
        json={"message": "내 결재 보여줘"},
    )

    assert response.status_code == 200, response.text
    items = response.json()["toolExecutions"][0]["result"]["items"]
    assert all(item["title"] != "관리자 소유 문서" for item in items)


def test_policy_tool_exposes_exact_search_citations(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_work_assistant_provider: FakeWorkAssistantProvider,
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    with session_factory() as db:
        index_active_policy_sections(
            db,
            fake_embedding_provider,
            fake_embedding_provider.model,
            fake_embedding_provider.dimensions,
        )
    fake_work_assistant_provider.planned_calls = [
        (
            "search_company_policy",
            {"query": "출장 숙박비 한도", "policyType": "TRAVEL", "topK": 4},
        )
    ]
    login(client, "seojin.yoon@jhworks.test")

    response = client.post(
        "/api/v1/work-assistant/query",
        json={"message": "출장 숙박비 한도가 얼마야?"},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["toolExecutions"][0]["result"]["status"] == "READY"
    assert any(item["sectionId"] == "TRAVEL-1" for item in result["policyCitations"])


def test_unknown_and_invalid_tools_are_rejected(
    session_factory: sessionmaker[Session],
    fake_embedding_provider: FakePolicyEmbeddingProvider,
) -> None:
    with session_factory() as db:
        actor = db.scalar(select(Employee).where(Employee.email == "seojin.yoon@jhworks.test"))
        assert actor is not None
        executor = ReadOnlyEnterpriseToolExecutor(db, actor, fake_embedding_provider)
        with pytest.raises(ToolExecutionError):
            executor.execute("submit_approval", {"approvalId": "apr_any"})
        with pytest.raises(ToolExecutionError):
            executor.execute("get_my_manager", {"employeeId": "emp_other"})


def test_public_tool_catalog_contains_no_write_tool() -> None:
    names = {tool["name"] for tool in TOOL_DEFINITIONS}

    assert names == {
        "get_current_employee",
        "get_my_manager",
        "list_my_approvals",
        "search_company_policy",
    }
    assert all(tool["strict"] is True for tool in TOOL_DEFINITIONS)


def test_provider_failure_returns_503_without_changes(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    session_factory: sessionmaker[Session],
    fake_work_assistant_provider: FakeWorkAssistantProvider,
) -> None:
    fake_work_assistant_provider.should_fail = True
    before = approval_count(session_factory)
    login(client, "seojin.yoon@jhworks.test")

    response = client.post(
        "/api/v1/work-assistant/query",
        json={"message": "내 결재 보여줘"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "WORK_ASSISTANT_UNAVAILABLE"
    assert approval_count(session_factory) == before


def test_work_assistant_eval_dataset_covers_every_read_only_tool() -> None:
    cases = load_cases()
    covered = {name for case in cases for name in case.expected_tool_names}

    assert len(cases) >= 5
    assert covered == {tool["name"] for tool in TOOL_DEFINITIONS}

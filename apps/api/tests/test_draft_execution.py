import logging
from collections.abc import Callable
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import ApprovalDraftCandidate, DraftIntent
from app.schemas.draft_execution import DraftStage, DraftStageOutcome
from app.services.draft_execution import DraftExecution
from tests.conftest import FakeApprovalDraftProvider
from tests.test_approval_draft_ai import approval_count


def test_execution_rejects_reordering_nesting_and_continuing_after_failure() -> None:
    run = DraftExecution()
    with pytest.raises(RuntimeError), run.stage(DraftStage.PROVIDER):
        pass
    with pytest.raises(ValueError), run.stage(DraftStage.INPUT):
        with pytest.raises(RuntimeError), run.stage(DraftStage.INPUT):
            pass
        raise ValueError("sensitive error text")
    with pytest.raises(RuntimeError), run.stage(DraftStage.PROVIDER):
        pass
    with pytest.raises(RuntimeError):
        run.finish("PREVIEW")
    trace = run.finish("FAILED")
    assert trace.stages[0].outcome == DraftStageOutcome.FAILED
    assert trace.outcome == "FAILED"
    assert "sensitive" not in trace.model_dump_json()
    with pytest.raises(RuntimeError):
        run.finish("FAILED")


def test_prepare_reports_stage_outcomes_without_claiming_fact_verification(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_draft_provider: FakeApprovalDraftProvider,
    session_factory: sessionmaker[Session],
    caplog: pytest.LogCaptureFixture,
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    before = approval_count(session_factory)
    fake_draft_provider.candidate = ApprovalDraftCandidate(
        intent=DraftIntent.EXPENSE,
        amount=170000,
    )
    with caplog.at_level(logging.INFO, logger="jhworks.draft_execution"):
        first = client.post(
            "/api/v1/approval-draft-assistant/prepare",
            json={"request": "PRIVATE-REQUEST CES 17만원 정산"},
        ).json()
    trace = first["execution"]
    assert [r["stage"] for r in trace["stages"]] == [s.value for s in DraftStage]
    assert trace["stages"][3]["outcome"] == "NEEDS_INPUT"
    assert trace["stages"][4]["outcome"] == "NOT_APPLICABLE"
    assert trace["stages"][5]["outcome"] == "NOT_APPLICABLE"
    assert trace["outcome"] == "NEEDS_INPUT"
    assert trace["model"] == "fake-draft-model"
    assert trace["promptVersion"]
    assert len(fake_draft_provider.inputs) == 1
    assert first["confirmationToken"] is None
    assert approval_count(session_factory) == before
    logs = " ".join(r.message for r in caplog.records if r.name == "jhworks.draft_execution")
    assert trace["runId"] in logs
    assert "PRIVATE-REQUEST" not in logs
    assert "seojin" not in logs
    second = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": "다시 경비 정산"},
    ).json()
    assert second["execution"]["runId"] != trace["runId"]


def test_provider_failure_is_terminal_and_exposes_only_safe_trace(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_draft_provider: FakeApprovalDraftProvider,
    session_factory: sessionmaker[Session],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    before = approval_count(session_factory)
    fake_draft_provider.should_fail = True
    response = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": "경비 정산"},
    )
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "AI_DRAFT_UNAVAILABLE"
    assert [r["stage"] for r in error["details"]["execution"]["stages"]] == [
        "input",
        "provider",
    ]
    assert error["details"]["execution"]["stages"][-1]["outcome"] == "FAILED"
    assert "fake provider failure" not in response.text
    assert approval_count(session_factory) == before


def test_schema_bypass_and_policy_exception_never_issue_confirmation(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_draft_provider: FakeApprovalDraftProvider,
    session_factory: sessionmaker[Session],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    before = approval_count(session_factory)
    fake_draft_provider.candidate = ApprovalDraftCandidate(
        intent=DraftIntent.GENERAL,
        title="협조",
        content="협조 요청",
    ).model_copy(update={"amount": -1})
    response = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": "협조 요청"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["details"]["execution"]["stages"][-1] == {
        "stage": "normalize",
        "outcome": "FAILED",
        "durationMs": response.json()["error"]["details"]["execution"]["stages"][-1]["durationMs"],
    }
    fake_draft_provider.candidate = ApprovalDraftCandidate(
        intent=DraftIntent.GENERAL,
        title="협조",
        content="협조 요청",
    )
    with patch("app.services.approval_draft._policy_context", side_effect=RuntimeError("PRIVATE")):
        response = client.post(
            "/api/v1/approval-draft-assistant/prepare",
            json={"request": "협조 요청"},
        )
    assert response.status_code == 503
    trace = response.json()["error"]["details"]["execution"]
    assert trace["stages"][-1]["stage"] == "policy"
    assert trace["stages"][-1]["outcome"] == "FAILED"
    assert "PRIVATE" not in response.text
    assert approval_count(session_factory) == before


def test_whitespace_request_stops_before_provider(
    client: TestClient,
    login: Callable[[TestClient, str], None],
    fake_draft_provider: FakeApprovalDraftProvider,
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    response = client.post(
        "/api/v1/approval-draft-assistant/prepare",
        json={"request": "   "},
    )
    assert response.status_code == 422
    trace = response.json()["error"]["details"]["execution"]
    assert len(trace["stages"]) == 1
    assert trace["stages"][0]["stage"] == "input"
    assert fake_draft_provider.inputs == []


def test_execution_cannot_promote_missing_information_to_preview() -> None:
    run = DraftExecution()
    for stage in DraftStage:
        with run.stage(stage) as result:
            if stage == DraftStage.VALIDATE:
                result.outcome = DraftStageOutcome.NEEDS_INPUT
            elif stage in {DraftStage.POLICY, DraftStage.PREVIEW}:
                result.outcome = DraftStageOutcome.NOT_APPLICABLE
    with pytest.raises(RuntimeError):
        run.finish("PREVIEW")
    assert run.finish("NEEDS_INPUT").outcome == "NEEDS_INPUT"

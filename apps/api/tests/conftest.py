from collections.abc import Callable, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.approval_draft import (
    ApprovalDraftCandidate,
    ApprovalDraftProviderError,
    ApprovalDraftProviderInput,
    DraftIntent,
    DraftProviderResult,
    DraftProviderUsage,
)
from app.ai.approval_review import (
    ApprovalReviewProviderError,
    ProviderReviewResult,
    ProviderUsage,
    ReviewDocument,
    SemanticReviewOutput,
)
from app.ai.leave_assistant import (
    LeaveAssistantCandidate,
    LeaveAssistantIntent,
    LeaveAssistantProviderError,
    LeaveAssistantProviderInput,
    LeaveAssistantProviderResult,
    LeaveAssistantProviderUsage,
)
from app.ai.policy_embedding import (
    EmbeddingResult,
    EmbeddingUsage,
    PolicyEmbeddingProviderError,
)
from app.ai.work_assistant import (
    EnterpriseToolExecutor,
    ToolExecution,
    ToolExecutionError,
    WorkAssistantProviderError,
    WorkAssistantProviderResult,
    WorkAssistantUsage,
)
from app.api.dependencies import (
    get_approval_draft_provider,
    get_approval_review_provider,
    get_leave_assistant_provider,
    get_policy_embedding_provider,
    get_work_assistant_provider,
)
from app.core.database import Base, get_db
from app.main import app
from app.scripts.seed import seed_database


class FakeApprovalReviewProvider:
    def __init__(self) -> None:
        self.output = SemanticReviewOutput(revised_content="검토 대상 본문입니다.")
        self.should_fail = False
        self.documents: list[ReviewDocument] = []
        self.safety_identifiers: list[str] = []

    def review(self, document: ReviewDocument, safety_identifier: str) -> ProviderReviewResult:
        if self.should_fail:
            raise ApprovalReviewProviderError("fake provider failure")
        self.documents.append(document)
        self.safety_identifiers.append(safety_identifier)
        return ProviderReviewResult(
            output=self.output,
            provider="fake",
            model="fake-review-model",
            usage=ProviderUsage(input_tokens=120, output_tokens=40, total_tokens=160),
            latency_ms=25,
        )


class FakeApprovalDraftProvider:
    def __init__(self) -> None:
        self.candidate = ApprovalDraftCandidate(
            intent=DraftIntent.GENERAL,
            title="업무 협조 요청",
            content="프로젝트 업무 협조를 요청합니다.",
        )
        self.should_fail = False
        self.inputs: list[ApprovalDraftProviderInput] = []
        self.safety_identifiers: list[str] = []

    def prepare(
        self,
        provider_input: ApprovalDraftProviderInput,
        safety_identifier: str,
    ) -> DraftProviderResult:
        if self.should_fail:
            raise ApprovalDraftProviderError("fake provider failure")
        self.inputs.append(provider_input)
        self.safety_identifiers.append(safety_identifier)
        return DraftProviderResult(
            candidate=self.candidate,
            provider="fake",
            model="fake-draft-model",
            usage=DraftProviderUsage(input_tokens=80, output_tokens=40, total_tokens=120),
            latency_ms=20,
        )


class FakeLeaveAssistantProvider:
    def __init__(self) -> None:
        self.candidate = LeaveAssistantCandidate(
            intent=LeaveAssistantIntent.RECOMMEND_DATES,
            search_start=None,
            search_end=None,
            requested_days=None,
        )
        self.should_fail = False
        self.inputs: list[LeaveAssistantProviderInput] = []
        self.safety_identifiers: list[str] = []

    def structure(
        self,
        provider_input: LeaveAssistantProviderInput,
        safety_identifier: str,
    ) -> LeaveAssistantProviderResult:
        if self.should_fail:
            raise LeaveAssistantProviderError("fake provider failure")
        self.inputs.append(provider_input)
        self.safety_identifiers.append(safety_identifier)
        return LeaveAssistantProviderResult(
            candidate=self.candidate,
            provider="fake",
            model="fake-leave-model",
            usage=LeaveAssistantProviderUsage(
                input_tokens=70,
                output_tokens=20,
                total_tokens=90,
            ),
            latency_ms=18,
        )


class FakePolicyEmbeddingProvider:
    dimensions = 1536
    model = "text-embedding-3-small"

    def __init__(self) -> None:
        self.should_fail = False
        self.texts: list[str] = []

    def _vector(self, text: str) -> list[float]:
        normalized = text.lower().replace(",", "")
        vector = [0.0] * self.dimensions
        keyword_groups = (
            ("accommodation", "lodging", "숙박"),
            ("transportation", "교통"),
            ("prior approval", "300000", "사전 승인"),
            ("client visit", "clientname", "visitpurpose", "고객사", "방문 목적"),
            ("meal", "식비"),
            ("receipt", "영수증"),
            ("leave", "휴가", "연차"),
        )
        for index, keywords in enumerate(keyword_groups):
            if any(keyword in normalized for keyword in keywords):
                vector[index] = 1.0
        if not any(vector):
            vector[-1] = 1.0
        return vector

    def embed(self, texts: list[str]) -> EmbeddingResult:
        if self.should_fail:
            raise PolicyEmbeddingProviderError("fake embedding failure")
        self.texts.extend(texts)
        return EmbeddingResult(
            vectors=[self._vector(text) for text in texts],
            provider="fake",
            model=self.model,
            usage=EmbeddingUsage(input_tokens=len(texts) * 10, total_tokens=len(texts) * 10),
            latency_ms=5,
        )


class FakeWorkAssistantProvider:
    def __init__(self) -> None:
        self.answer_text = "조회 결과입니다."
        self.planned_calls: list[tuple[str, dict[str, Any]]] = []
        self.should_fail = False
        self.messages: list[str] = []
        self.safety_identifiers: list[str] = []

    def answer(
        self,
        message: str,
        executor: EnterpriseToolExecutor,
        safety_identifier: str,
    ) -> WorkAssistantProviderResult:
        if self.should_fail:
            raise WorkAssistantProviderError("fake provider failure")
        self.messages.append(message)
        self.safety_identifiers.append(safety_identifier)
        executions: list[ToolExecution] = []
        try:
            for name, arguments in self.planned_calls:
                result = executor.execute(name, arguments)
                executions.append(
                    ToolExecution(name=name, arguments=arguments, result=result)
                )
        except ToolExecutionError as exc:
            raise WorkAssistantProviderError("fake invalid tool call") from exc
        return WorkAssistantProviderResult(
            answer=self.answer_text,
            executions=executions,
            provider="fake",
            model="fake-tool-model",
            usage=WorkAssistantUsage(input_tokens=100, output_tokens=30, total_tokens=130),
            latency_ms=30,
            round_count=2 if executions else 1,
        )


@pytest.fixture
def session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with factory() as db:
        seed_database(db)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def fake_review_provider() -> FakeApprovalReviewProvider:
    return FakeApprovalReviewProvider()


@pytest.fixture
def fake_draft_provider() -> FakeApprovalDraftProvider:
    return FakeApprovalDraftProvider()


@pytest.fixture
def fake_leave_assistant_provider() -> FakeLeaveAssistantProvider:
    return FakeLeaveAssistantProvider()


@pytest.fixture
def fake_embedding_provider() -> FakePolicyEmbeddingProvider:
    return FakePolicyEmbeddingProvider()


@pytest.fixture
def fake_work_assistant_provider() -> FakeWorkAssistantProvider:
    return FakeWorkAssistantProvider()


@pytest.fixture
def client(
    session_factory: sessionmaker[Session],
    fake_draft_provider: FakeApprovalDraftProvider,
    fake_leave_assistant_provider: FakeLeaveAssistantProvider,
    fake_review_provider: FakeApprovalReviewProvider,
    fake_embedding_provider: FakePolicyEmbeddingProvider,
    fake_work_assistant_provider: FakeWorkAssistantProvider,
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_approval_draft_provider] = lambda: fake_draft_provider
    app.dependency_overrides[get_leave_assistant_provider] = (
        lambda: fake_leave_assistant_provider
    )
    app.dependency_overrides[get_approval_review_provider] = lambda: fake_review_provider
    app.dependency_overrides[get_policy_embedding_provider] = lambda: fake_embedding_provider
    app.dependency_overrides[get_work_assistant_provider] = lambda: fake_work_assistant_provider
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def login() -> Callable[[TestClient, str], None]:
    def _login(client: TestClient, email: str) -> None:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "demo1234"},
        )
        assert response.status_code == 200, response.text

    return _login

from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.approval_review import (
    ApprovalReviewProviderError,
    ProviderReviewResult,
    ProviderUsage,
    ReviewDocument,
    SemanticReviewOutput,
)
from app.api.dependencies import get_approval_review_provider
from app.core.database import Base, get_db
from app.main import app
from app.scripts.seed import seed_database


class FakeApprovalReviewProvider:
    def __init__(self) -> None:
        self.output = SemanticReviewOutput()
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
def client(
    session_factory: sessionmaker[Session],
    fake_review_provider: FakeApprovalReviewProvider,
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_approval_review_provider] = lambda: fake_review_provider
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

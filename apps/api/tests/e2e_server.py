"""Isolated browser fixture: real API/domain/DB, synthetic providers, no paid calls.

Run only via Playwright. Never mount this fixture in a deployment.
"""
from collections.abc import Generator
from datetime import datetime, timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.ai.leave_assistant import LeaveAssistantCandidate, LeaveAssistantIntent
from app.api.dependencies import get_leave_assistant_provider, get_policy_embedding_provider
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.scripts.seed import seed_database
from app.services.policy_retrieval import index_active_policy_sections

settings = get_settings()
settings.openai_api_key = None
settings.frontend_origin = "http://localhost:3100"

# Import after the test-only configuration; existing databases are never used.
from app.main import app  # noqa: E402
from tests.conftest import (  # noqa: E402
    FakeLeaveAssistantProvider,
    FakePolicyEmbeddingProvider,
)

database_dir = TemporaryDirectory(prefix="jhworks-browser-")
engine = create_engine(
    f"sqlite:///{database_dir.name}/fixture.db", connect_args={"check_same_thread": False},
)
factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base.metadata.create_all(engine)
embedding = FakePolicyEmbeddingProvider()
with factory() as db:
    seed_database(db)
    index_active_policy_sections(db, embedding, embedding.model, embedding.dimensions)


class BrowserLeaveProvider(FakeLeaveAssistantProvider):
    def __init__(self) -> None:
        super().__init__()
        today = datetime.now(ZoneInfo("Asia/Seoul")).date()
        monday = today + timedelta(days=7 - today.weekday())
        self.candidate = LeaveAssistantCandidate(
            intent=LeaveAssistantIntent.RECOMMEND_DATES,
            search_start=monday, search_end=monday + timedelta(days=4),
            requested_days=Decimal("2.0"),
        )


def test_db() -> Generator[Session, None, None]:
    with factory() as db:
        yield db


app.dependency_overrides[get_db] = test_db
app.dependency_overrides[get_leave_assistant_provider] = BrowserLeaveProvider
app.dependency_overrides[get_policy_embedding_provider] = lambda: embedding

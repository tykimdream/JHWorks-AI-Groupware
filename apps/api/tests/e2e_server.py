"""Isolated browser fixture: real API/domain/DB, synthetic providers, no paid calls.

Run only via Playwright. Never mount this fixture in a deployment.
"""

import os
import re
from collections.abc import Generator
from contextlib import suppress
from datetime import datetime, timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import (
    ApprovalDraftCandidate,
    ApprovalDraftProviderInput,
    DraftIntent,
    DraftProviderResult,
)
from app.ai.leave_assistant import LeaveAssistantCandidate, LeaveAssistantIntent
from app.api.dependencies import (
    get_ai_capabilities,
    get_approval_draft_provider,
    get_leave_assistant_provider,
    get_policy_embedding_provider,
)
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.models.employee import Employee
from app.models.enums import ExpenseCategory
from app.schemas.approval import ApprovalCreate
from app.scripts.seed import seed_database
from app.services.approval import create_draft
from app.services.policy_retrieval import index_active_policy_sections

settings = get_settings()
settings.openai_api_key = None
settings.frontend_origin = "http://localhost:3100"
# The full desktop/mobile suite can legitimately authenticate more than 60 times/minute.
# Keep the production limiter intact; this isolated synthetic fixture uses its supported ceiling.
settings.login_requests_per_minute = 600

# Import after the test-only configuration; existing databases are never used.
from app.main import app  # noqa: E402
from tests.conftest import (  # noqa: E402
    FakeApprovalDraftProvider,
    FakeLeaveAssistantProvider,
    FakePolicyEmbeddingProvider,
)

# Advertise only synthetic provider capabilities; keep every real API key absent.
if not settings.public_demo_enabled:
    from app.schemas.demo import AICapabilities

    app.dependency_overrides[get_ai_capabilities] = lambda: AICapabilities(
        approval_draft=True,
        leave_assistant=True,
        policy_embedding=True,
    )

database_dir = TemporaryDirectory(prefix="jhworks-browser-")
engine = create_engine(
    f"sqlite:///{database_dir.name}/fixture.db",
    connect_args={"check_same_thread": False},
)
factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base.metadata.create_all(engine)
embedding = FakePolicyEmbeddingProvider()
with factory() as db:
    seed_database(db)
    index_active_policy_sections(db, embedding, embedding.model, embedding.dimensions)
    if (
        os.environ.get("JHWORKS_BROWSER_SAMPLE_EXPENSES") == "1"
        and not settings.public_demo_enabled
    ):
        actor = db.get(Employee, "emp_sales_001")
        assert actor is not None
        for title, purpose in [
            ("CES 교통비 · 기존 합성 예시", "CES 협력사 방문"),
            ("CES 교통비 · 제출 전 합성 예시", ""),
        ]:
            create_draft(
                db,
                actor,
                ApprovalCreate.model_validate(
                    {
                        "type": "EXPENSE",
                        "title": title,
                        "content": "사전 점검 화면을 위한 합성 예시입니다.",
                        "amount": 170000,
                        "details": {
                            "kind": "EXPENSE",
                            "expenseDate": datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat(),
                            "merchant": "코레일 · 합성 예시",
                            "category": "TRANSPORTATION",
                            "purpose": purpose,
                        },
                    }
                ),
            )


class BrowserLeaveProvider(FakeLeaveAssistantProvider):
    def __init__(self) -> None:
        super().__init__()
        today = datetime.now(ZoneInfo("Asia/Seoul")).date()
        monday = today + timedelta(days=7 - today.weekday())
        self.candidate = LeaveAssistantCandidate(
            intent=LeaveAssistantIntent.RECOMMEND_DATES,
            search_start=monday,
            search_end=monday + timedelta(days=4),
            requested_days=Decimal("2.0"),
        )


class BrowserDraftProvider(FakeApprovalDraftProvider):
    """Scripted UI scenario, explicitly not an actual language model evaluation."""

    def prepare(
        self,
        provider_input: ApprovalDraftProviderInput,
        safety_identifier: str,
    ) -> DraftProviderResult:
        if "CES 출장에서 쓴 17만원" in provider_input.request:
            answer = " ".join(provider_input.answers)
            match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", answer)
            paid = None
            if match:
                with suppress(ValueError):
                    paid = datetime.strptime(match[0], "%Y-%m-%d").date()
            self.candidate = ApprovalDraftCandidate(
                intent=DraftIntent.EXPENSE,
                title="CES 출장 경비 정산",
                content="CES 출장에서 실제 지출한 170,000원의 정산을 요청합니다.",
                amount=170000,
                expense_date=paid,
                merchant="코레일" if "코레일" in answer else None,
                expense_category=ExpenseCategory.TRANSPORTATION if "교통비" in answer else None,
                expense_purpose="CES 출장",
                receipt_reference="RCP-CES-001" if "RCP-CES-001" in answer else None,
            )
        elif "CES 협력사 미팅" in provider_input.request:
            today = provider_input.current_date
            tuesday = today + timedelta(days=7 - today.weekday() + 1)
            self.candidate = ApprovalDraftCandidate(
                intent=DraftIntent.BUSINESS_TRIP,
                title="CES 협력사 미팅 출장 신청",
                content=(
                    "부산 CES 협력사 미팅을 위한 출장 승인을 요청합니다. "
                    "예상 교통비는 170,000원입니다."
                ),
                destination="부산",
                start_date=tuesday,
                end_date=(
                    tuesday if any("당일" in answer for answer in provider_input.answers) else None
                ),
                amount=170000,
                transportation=170000,
                client_name="CES 협력사 미팅",
                visit_purpose="CES 협력사 미팅",
            )
        elif "전시 부스 제작 협조" in provider_input.request:
            self.candidate = ApprovalDraftCandidate(
                intent=DraftIntent.GENERAL,
                title="CES 전시 부스 제작 협조 요청",
                content="CES 참가 준비를 위해 디자인팀에 전시 부스 제작 협조를 요청합니다.",
            )
        else:
            self.candidate = ApprovalDraftCandidate(
                intent=DraftIntent.UNSUPPORTED,
            )
        return super().prepare(provider_input, safety_identifier)


def test_db() -> Generator[Session, None, None]:
    with factory() as db:
        yield db


app.dependency_overrides[get_db] = test_db
app.dependency_overrides[get_leave_assistant_provider] = BrowserLeaveProvider
app.dependency_overrides[get_approval_draft_provider] = BrowserDraftProvider
app.dependency_overrides[get_policy_embedding_provider] = lambda: embedding

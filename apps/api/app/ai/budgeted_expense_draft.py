"""Reserve before constructing/calling the pinned public draft provider. No paid embeddings."""

from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.ai.approval_draft import (
    ApprovalDraftProvider,
    ApprovalDraftProviderError,
    ApprovalDraftProviderInput,
    DraftProviderResult,
)
from app.ai.expense_pricing import MAX_REQUEST_MICRO_USD, MODEL, micro_usd
from app.core.ai_budget import AIBudgetLimits
from app.services import ai_budget


class BudgetedExpenseDraftProvider:
    def __init__(
        self,
        *,
        workspace_id: str,
        factory: sessionmaker[Session],
        provider_factory: Callable[[], ApprovalDraftProvider],
        limits: AIBudgetLimits,
        check_authorization: Callable[[Session], None],
    ) -> None:
        self._workspace_id = workspace_id
        self._factory = factory
        self._provider_factory = provider_factory
        self._limits = limits
        self._check_authorization = check_authorization

    def prepare(
        self, provider_input: ApprovalDraftProviderInput, safety_identifier: str
    ) -> DraftProviderResult:
        if (
            len(provider_input.request) > 2000
            or len(provider_input.answers) > 8
            or any(len(answer) > 2000 for answer in provider_input.answers)
        ):
            raise ApprovalDraftProviderError("Expense AI input exceeds the supported limit")
        with self._factory() as db:
            receipt = ai_budget.reserve(
                db,
                workspace_id=self._workspace_id,
                maximum_micro_usd=MAX_REQUEST_MICRO_USD,
                limits=self._limits,
            )
        try:
            with self._factory() as db:
                self._check_authorization(db)
        except Exception:
            # Provider construction has not begun: no paid attempt occurred.
            with self._factory() as db:
                ai_budget.settle(db, receipt.id, actual_micro_usd=0)
            raise
        try:
            result = self._provider_factory().prepare(provider_input, safety_identifier)
        except Exception:
            # SDK retry count is zero. A timeout/parse/connection failure is not proof of no bill.
            with self._factory() as db:
                ai_budget.settle(db, receipt.id, actual_micro_usd=None)
            raise ApprovalDraftProviderError("Expense AI provider is unavailable") from None
        usage = result.usage
        verified = result.model == MODEL and result.service_tier == "default"
        try:
            cost = micro_usd(usage.input_tokens, usage.output_tokens)
            valid_usage = (
                usage.known
                and usage.input_tokens > 0
                and type(usage.total_tokens) is int
                and usage.total_tokens == usage.input_tokens + usage.output_tokens
            )
        except ValueError:
            cost, valid_usage = 0, False
        with self._factory() as db:
            ai_budget.settle(
                db,
                receipt.id,
                actual_micro_usd=cost if verified and valid_usage else None,
                freeze=not verified or not valid_usage,
            )
        if not verified or not valid_usage:
            raise ApprovalDraftProviderError("Expense AI accounting could not be verified")
        return result

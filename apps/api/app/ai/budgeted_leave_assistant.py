"""Account for every public leave model call using the shared demo budget."""

import hashlib
from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.ai.expense_pricing import MAX_REQUEST_MICRO_USD, MODEL, micro_usd
from app.ai.leave_assistant import (
    LeaveAssistantProvider,
    LeaveAssistantProviderError,
    LeaveAssistantProviderInput,
    LeaveAssistantProviderResult,
)
from app.core.ai_budget import AIBudgetLimits
from app.services import ai_budget


class BudgetedLeaveAssistantProvider:
    def __init__(
        self,
        *,
        workspace_id: str,
        factory: sessionmaker[Session],
        provider_factory: Callable[[], LeaveAssistantProvider],
        limits: AIBudgetLimits,
        check_authorization: Callable[[Session], None],
    ) -> None:
        self._workspace_id = workspace_id
        self._factory = factory
        self._provider_factory = provider_factory
        self._limits = limits
        self._check_authorization = check_authorization

    def structure(
        self, provider_input: LeaveAssistantProviderInput, safety_identifier: str
    ) -> LeaveAssistantProviderResult:
        if (
            len(provider_input.request) > 2000
            or len(provider_input.answers) > 8
            or any(len(answer) > 2000 for answer in provider_input.answers)
        ):
            raise LeaveAssistantProviderError("Leave AI input exceeds the supported limit")
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
            with self._factory() as db:
                ai_budget.settle(db, receipt.id, actual_micro_usd=0)
            raise
        try:
            result = self._provider_factory().structure(
                provider_input, hashlib.sha256(safety_identifier.encode()).hexdigest()
            )
        except Exception:
            with self._factory() as db:
                ai_budget.settle(db, receipt.id, actual_micro_usd=None)
            raise LeaveAssistantProviderError("Leave AI provider is unavailable") from None
        usage = result.usage
        verified = result.model == MODEL and result.service_tier == "default"
        try:
            cost = micro_usd(usage.input_tokens, usage.output_tokens)
            valid_usage = (
                usage.input_tokens > 0
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
            raise LeaveAssistantProviderError("Leave AI accounting could not be verified")
        return result

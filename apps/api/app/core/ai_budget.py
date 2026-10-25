"""Configuration-only budget types; no DB/provider imports."""

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class AIBudgetLimits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # No production defaults: real budgets and a verified upper-bound estimator are required.
    day_micro_usd: StrictInt = Field(ge=1, le=10**12)
    month_micro_usd: StrictInt = Field(ge=1, le=10**12)
    day_admissions: StrictInt = Field(ge=1, le=10000)
    scope_day_admissions: StrictInt = Field(ge=1, le=1000)
    concurrent_requests: StrictInt = Field(ge=1, le=100)

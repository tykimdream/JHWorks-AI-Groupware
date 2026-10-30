from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.ai_budget import AIBudgetLimits

AICapability = Literal[
    "approval_draft", "approval_review", "leave_assistant", "work_assistant", "policy_embedding"
]
AI_CAPABILITIES: tuple[AICapability, ...] = (
    "approval_draft",
    "approval_review",
    "leave_assistant",
    "work_assistant",
    "policy_embedding",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_prefix="JHWORKS_",
        extra="ignore",
    )

    app_name: str = "JHWorks API"
    environment: str = "development"
    log_format: Literal["json", "text"] = "json"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: str = "sqlite:///./jhworks.db"
    database_pool_mode: Literal["queue", "null"] = "queue"
    database_pool_size: int = Field(default=2, ge=1, le=20)
    database_max_overflow: int = Field(default=0, ge=0, le=20)
    database_pool_timeout_seconds: float = Field(default=5, ge=1, le=30)
    database_disable_prepared_statements: bool = False
    jwt_secret: str = "local-development-only-change-me"
    jwt_algorithm: str = "HS256"
    session_cookie_name: str = "jhworks_session"
    public_demo_enabled: bool = False
    demo_starts_per_day: int = Field(default=20, ge=1, le=100)
    demo_retained_workspaces: int = Field(default=30, ge=1, le=100)
    demo_ttl_minutes: int = Field(default=15, ge=5, le=30)
    login_requests_per_minute: int = Field(default=60, ge=1, le=600)
    session_ttl_minutes: int = 480
    frontend_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    cookie_samesite: str = Field(default="lax", pattern="^(lax|strict|none)$")
    openai_api_key: SecretStr | None = None
    ai_enabled: bool = True
    public_expense_ai_enabled: bool = False
    public_leave_ai_enabled: bool = False
    public_expense_ai_budget: AIBudgetLimits | None = None
    ai_capabilities: frozenset[AICapability] = frozenset(AI_CAPABILITIES)
    openai_model: str = "gpt-5.4-mini"
    ai_review_timeout_seconds: float = Field(default=20.0, ge=1.0, le=60.0)
    approval_draft_confirmation_ttl_minutes: int = Field(default=15, ge=1, le=60)
    leave_draft_confirmation_ttl_minutes: int = Field(default=15, ge=1, le=60)
    leave_submit_confirmation_ttl_minutes: int = Field(default=10, ge=1, le=60)
    local_example_search_enabled: bool = False
    policy_embedding_model: str = "text-embedding-3-small"
    policy_embedding_dimensions: int = Field(default=1536, ge=256, le=3072)
    policy_retrieval_top_k: int = Field(default=4, ge=1, le=10)
    policy_retrieval_min_score: float = Field(default=0.15, ge=-1.0, le=1.0)

    def allows_ai(self, capability: AICapability) -> bool:
        key_present = self.openai_api_key is not None and bool(
            self.openai_api_key.get_secret_value().strip()
        )
        if self.public_demo_enabled:
            return (
                not self.ai_enabled
                and self.public_expense_ai_budget is not None
                and (
                    (capability == "approval_draft" and self.public_expense_ai_enabled)
                    or (capability == "leave_assistant" and self.public_leave_ai_enabled)
                )
                and capability in self.ai_capabilities
                and key_present
            )
        return self.ai_enabled and capability in self.ai_capabilities and key_present

    @model_validator(mode="after")
    def validate_public_demo_safety(self) -> Self:
        if self.public_demo_enabled and self.ai_enabled:
            raise ValueError("Public demo requires JHWORKS_AI_ENABLED=false")
        if self.public_expense_ai_enabled or self.public_leave_ai_enabled:
            budget = self.public_expense_ai_budget
            if not self.public_demo_enabled or budget is None:
                raise ValueError("Public expense AI requires public demo and explicit budget")
            # Deliberate rollout ceiling, not a default paid budget. No activation by key alone.
            if not (
                307200 <= budget.day_micro_usd <= 500000
                and budget.day_micro_usd <= budget.month_micro_usd <= 2000000
                and budget.day_admissions <= 10
                and budget.scope_day_admissions <= 5
                and budget.concurrent_requests == 1
            ):
                raise ValueError("Public expense AI budget exceeds rollout limits")
        return self

    @model_validator(mode="after")
    def validate_production_safety(self) -> Self:
        if self.environment.lower() not in {"production", "prod"}:
            return self
        errors: list[str] = []
        if len(self.jwt_secret) < 32 or self.jwt_secret == "local-development-only-change-me":
            errors.append("JHWORKS_JWT_SECRET must be a non-default value of 32+ characters")
        if not self.cookie_secure:
            errors.append("JHWORKS_COOKIE_SECURE must be true")
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            errors.append("JHWORKS_DATABASE_URL must use PostgreSQL")
        origin = urlparse(self.frontend_origin)
        if origin.scheme != "https" or not origin.netloc or origin.path not in {"", "/"}:
            errors.append("JHWORKS_FRONTEND_ORIGIN must be an HTTPS origin without a path")
        if errors:
            raise ValueError("Invalid production configuration: " + "; ".join(errors))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    login_requests_per_minute: int = Field(default=60, ge=1, le=600)
    session_ttl_minutes: int = 480
    frontend_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    cookie_samesite: str = Field(default="lax", pattern="^(lax|strict|none)$")
    openai_api_key: SecretStr | None = None
    ai_enabled: bool = True
    openai_model: str = "gpt-5.4-mini"
    ai_review_timeout_seconds: float = Field(default=20.0, ge=1.0, le=60.0)
    approval_draft_confirmation_ttl_minutes: int = Field(default=15, ge=1, le=60)
    leave_draft_confirmation_ttl_minutes: int = Field(default=15, ge=1, le=60)
    leave_submit_confirmation_ttl_minutes: int = Field(default=10, ge=1, le=60)
    policy_embedding_model: str = "text-embedding-3-small"
    policy_embedding_dimensions: int = Field(default=1536, ge=256, le=3072)
    policy_retrieval_top_k: int = Field(default=4, ge=1, le=10)
    policy_retrieval_min_score: float = Field(default=0.15, ge=-1.0, le=1.0)

    @model_validator(mode="after")
    def validate_production_safety(self) -> Self:
        if self.environment.lower() not in {"production", "prod"}:
            return self
        errors: list[str] = []
        if (
            len(self.jwt_secret) < 32
            or self.jwt_secret == "local-development-only-change-me"
        ):
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

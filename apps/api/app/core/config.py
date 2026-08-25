from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_prefix="JHWORKS_",
        extra="ignore",
    )

    app_name: str = "JHWorks API"
    environment: str = "development"
    database_url: str = "sqlite:///./jhworks.db"
    jwt_secret: str = "local-development-only-change-me"
    jwt_algorithm: str = "HS256"
    session_cookie_name: str = "jhworks_session"
    session_ttl_minutes: int = 480
    frontend_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    cookie_samesite: str = Field(default="lax", pattern="^(lax|strict|none)$")
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.4-mini"
    ai_review_timeout_seconds: float = Field(default=20.0, ge=1.0, le=60.0)
    policy_embedding_model: str = "text-embedding-3-small"
    policy_embedding_dimensions: int = Field(default=1536, ge=256, le=3072)
    policy_retrieval_top_k: int = Field(default=4, ge=1, le=10)
    policy_retrieval_min_score: float = Field(default=0.15, ge=-1.0, le=1.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()

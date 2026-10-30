from app.ai.openai_policy_embedding import OpenAIPolicyEmbeddingProvider
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.approval_examples import index_examples


def main() -> None:
    settings = get_settings()
    key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if not key:
        raise SystemExit("JHWORKS_OPENAI_API_KEY is required to index examples")
    provider = OpenAIPolicyEmbeddingProvider(
        key,
        settings.policy_embedding_model,
        settings.policy_embedding_dimensions,
        settings.ai_review_timeout_seconds,
    )
    with SessionLocal() as db:
        count = index_examples(
            db, provider, settings.policy_embedding_model, settings.policy_embedding_dimensions
        )
    print(f"approval_examples_indexed={count}")


if __name__ == "__main__":
    main()

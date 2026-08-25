from app.ai.openai_policy_embedding import OpenAIPolicyEmbeddingProvider
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.policy_retrieval import index_active_policy_sections


def main() -> None:
    settings = get_settings()
    api_key = settings.openai_api_key
    secret = api_key.get_secret_value() if api_key else ""
    if not secret:
        raise SystemExit("JHWORKS_OPENAI_API_KEY is required to index policies")

    provider = OpenAIPolicyEmbeddingProvider(
        api_key=secret,
        model=settings.policy_embedding_model,
        dimensions=settings.policy_embedding_dimensions,
        timeout_seconds=settings.ai_review_timeout_seconds,
    )
    with SessionLocal() as db:
        indexed, skipped, model, total_tokens = index_active_policy_sections(
            db,
            provider,
            settings.policy_embedding_model,
            settings.policy_embedding_dimensions,
        )
    print(
        f"policy_index_completed indexed={indexed} skipped={skipped} "
        f"model={model} total_tokens={total_tokens}"
    )


if __name__ == "__main__":
    main()

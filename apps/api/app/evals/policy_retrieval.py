import json
from pathlib import Path

from pydantic import Field

from app.ai.openai_policy_embedding import OpenAIPolicyEmbeddingProvider
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.schema import ApiSchema
from app.models.enums import PolicyType
from app.schemas.policy import PolicyRetrievalStatus
from app.services.policy_retrieval import index_active_policy_sections, search_policy_sections

DATASET_PATH = Path(__file__).parents[2] / "evals" / "policy_retrieval_cases.json"


class PolicyRetrievalEvalCase(ApiSchema):
    id: str
    query: str
    policy_type: PolicyType
    expected_section_ids: list[str] = Field(min_length=1)


def load_cases() -> list[PolicyRetrievalEvalCase]:
    raw = json.loads(DATASET_PATH.read_text())
    return [PolicyRetrievalEvalCase.model_validate(item) for item in raw]


def main() -> None:
    settings = get_settings()
    api_key = settings.openai_api_key
    secret = api_key.get_secret_value() if api_key else ""
    if not secret:
        raise SystemExit("JHWORKS_OPENAI_API_KEY is required for the policy RAG evaluation")

    provider = OpenAIPolicyEmbeddingProvider(
        api_key=secret,
        model=settings.policy_embedding_model,
        dimensions=settings.policy_embedding_dimensions,
        timeout_seconds=settings.ai_review_timeout_seconds,
    )
    cases = load_cases()
    outcomes: list[dict[str, object]] = []
    with SessionLocal() as db:
        index_active_policy_sections(
            db,
            provider,
            settings.policy_embedding_model,
            settings.policy_embedding_dimensions,
        )
        for case in cases:
            result = search_policy_sections(
                db=db,
                query=case.query,
                policy_type=case.policy_type,
                top_k=settings.policy_retrieval_top_k,
                min_score=settings.policy_retrieval_min_score,
                provider=provider,
                expected_model=settings.policy_embedding_model,
                expected_dimensions=settings.policy_embedding_dimensions,
            )
            actual_ids = [item.section_id for item in result.items]
            hit = result.status == PolicyRetrievalStatus.READY and all(
                expected in actual_ids for expected in case.expected_section_ids
            )
            outcomes.append(
                {
                    "id": case.id,
                    "hit": hit,
                    "expectedSectionIds": case.expected_section_ids,
                    "actualSectionIds": actual_ids,
                    "status": result.status.value,
                    "latencyMs": result.latency_ms,
                    "inputTokens": result.usage.input_tokens,
                }
            )

    hit_count = sum(1 for outcome in outcomes if outcome["hit"])
    summary = {
        "model": settings.policy_embedding_model,
        "topK": settings.policy_retrieval_top_k,
        "hitRateAtK": hit_count / len(outcomes),
        "passed": hit_count,
        "total": len(outcomes),
        "cases": outcomes,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if hit_count != len(outcomes):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

from time import perf_counter

from openai import OpenAI, OpenAIError

from app.ai.policy_embedding import (
    EmbeddingResult,
    EmbeddingUsage,
    PolicyEmbeddingProviderError,
)


class OpenAIPolicyEmbeddingProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        dimensions: int,
        timeout_seconds: float,
    ) -> None:
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self._model = model
        self._dimensions = dimensions

    def embed(self, texts: list[str]) -> EmbeddingResult:
        started_at = perf_counter()
        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=texts,
                dimensions=self._dimensions,
                encoding_format="float",
            )
        except OpenAIError as exc:
            raise PolicyEmbeddingProviderError(
                "The policy embedding provider is unavailable"
            ) from exc

        vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        if len(vectors) != len(texts):
            raise PolicyEmbeddingProviderError(
                "The policy embedding provider returned no usable result"
            )

        return EmbeddingResult(
            vectors=vectors,
            provider="openai",
            model=response.model or self._model,
            usage=EmbeddingUsage(
                input_tokens=response.usage.prompt_tokens,
                total_tokens=response.usage.total_tokens,
            ),
            latency_ms=round((perf_counter() - started_at) * 1000),
        )

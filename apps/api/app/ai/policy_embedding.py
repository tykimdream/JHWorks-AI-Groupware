from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmbeddingUsage:
    input_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    provider: str
    model: str
    usage: EmbeddingUsage
    latency_ms: int


class PolicyEmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> EmbeddingResult: ...


class PolicyEmbeddingProviderError(Exception):
    """Safe provider boundary error that does not expose vendor details."""


class UnavailablePolicyEmbeddingProvider:
    def embed(self, texts: list[str]) -> EmbeddingResult:
        del texts
        raise PolicyEmbeddingProviderError("Policy embedding is not configured")

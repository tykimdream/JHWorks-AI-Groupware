"""Curated synthetic examples used as untrusted writing references."""

import hashlib
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.policy_embedding import PolicyEmbeddingProvider, PolicyEmbeddingProviderError
from app.models.approval_example import ApprovalExample

# This allowlist contains only curated, fictional, placeholder-only drafts.
from app.services.approval_example_corpus import EXAMPLES
from app.services.draft_privacy import TOPICS


def _digest(title: str, content: str) -> str:
    return hashlib.sha256(f"{title}\n{content}".encode()).hexdigest()


def index_examples(
    db: Session, provider: PolicyEmbeddingProvider, model: str, dimensions: int
) -> int:
    pending = []
    for key, title, content, outline in EXAMPLES:
        row = db.get(ApprovalExample, key)
        if row is None:
            row = ApprovalExample(id=key, title=title, content=content, outline=outline)
            db.add(row)
        row.title, row.content, row.outline = title, content, outline
        digest = _digest(title, content)
        if (
            row.embedding is None
            or row.embedding_model != model
            or row.content_hash != digest
            or len(row.embedding) != dimensions
        ):
            pending.append((row, digest))
    if pending:
        result = provider.embed([f"{row.title}\n{row.content}" for row, _ in pending])
        if (
            result.model != model
            or len(result.vectors) != len(pending)
            or any(
                len(v) != dimensions or not all(math.isfinite(x) for x in v) for v in result.vectors
            )
        ):
            raise PolicyEmbeddingProviderError("Invalid example embedding")
        for (row, digest), vector in zip(pending, result.vectors, strict=True):
            row.embedding, row.embedding_model, row.content_hash = vector, model, digest
    db.commit()
    return len(pending)


def search_examples(
    db: Session, provider: PolicyEmbeddingProvider, query: str, model: str, dimensions: int
) -> tuple[str, list[ApprovalExample]]:
    # Search embeds only fixed topic words, never the original user input.
    safe_words = set(" ".join(TOPICS.values()).split()) | {"일반", "업무", "기안"}
    if not query or any(word not in safe_words for word in query.split()):
        raise ValueError("Example retrieval accepts only server-owned topic hints")
    # Limit retrieval to the known synthetic corpus, not arbitrary or private documents.
    allowed = {entry[0]: entry for entry in EXAMPLES}
    rows = [
        row
        for row in db.scalars(select(ApprovalExample)).all()
        if row.id in allowed
        and row.embedding_model == model
        and row.embedding is not None
        and len(row.embedding) == dimensions
        and row.content_hash == _digest(allowed[row.id][1], allowed[row.id][2])
        and row.title == allowed[row.id][1]
        and row.content == allowed[row.id][2]
        and row.outline == allowed[row.id][3]
    ]
    if not rows:
        return "NOT_INDEXED", []
    try:
        result = provider.embed([query])
        if (
            result.model != model
            or len(result.vectors) != 1
            or len(result.vectors[0]) != dimensions
            or not all(math.isfinite(x) for x in result.vectors[0])
        ):
            return "UNAVAILABLE", []
        query_vector = result.vectors[0]
        query_norm = math.sqrt(sum(x * x for x in query_vector))
        if not query_norm:
            return "UNAVAILABLE", []
        scored = []
        for row in rows:
            vector = row.embedding or []
            if not all(math.isfinite(x) for x in vector):
                continue
            norm = math.sqrt(sum(x * x for x in vector))
            if norm:
                score = sum(a * b for a, b in zip(query_vector, vector, strict=True)) / (
                    query_norm * norm
                )
                if score >= 0.3:
                    scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return "READY", [row for _, row in scored[:2]]
    except PolicyEmbeddingProviderError:
        return "UNAVAILABLE", []

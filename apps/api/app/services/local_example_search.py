"""Optional loopback-only example retrieval. User text never leaves this machine here."""

import hashlib
import http.client
import json
import math
import threading
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.approval_example import ApprovalExample
from app.services.approval_example_corpus import EXAMPLES

MODEL = "bge-m3:latest"
DIMENSIONS = 1024
MAX_RESPONSE_BYTES = 2_000_000
_cache_lock = threading.Lock()
_cache_key: str | None = None
_cache_vectors: list[list[float]] | None = None


class LocalSearchUnavailable(Exception):
    pass


def _embed(texts: list[str]) -> list[list[float]]:
    payload = json.dumps(
        {"model": MODEL, "input": texts, "truncate": False}, ensure_ascii=False
    ).encode("utf-8")
    # Fixed numeric loopback address and direct HTTP: no configurable endpoint or redirects.
    connection = http.client.HTTPConnection("127.0.0.1", 11434, timeout=15)
    try:
        connection.request(
            "POST", "/api/embed", body=payload, headers={"Content-Type": "application/json"}
        )
        response = connection.getresponse()
        if response.status != 200:
            raise LocalSearchUnavailable("Local embeddings unavailable")
        data: Any = json.loads(response.read(MAX_RESPONSE_BYTES + 1))
        vectors = data.get("embeddings") if isinstance(data, dict) else None
        if (
            not isinstance(vectors, list)
            or len(vectors) != len(texts)
            or any(
                not isinstance(v, list)
                or len(v) != DIMENSIONS
                or any(type(x) not in (int, float) or not math.isfinite(x) for x in v)
                for v in vectors
            )
        ):
            raise LocalSearchUnavailable("Invalid local embeddings")
        return vectors
    except (OSError, ValueError, http.client.HTTPException) as exc:
        raise LocalSearchUnavailable("Local embeddings unavailable") from exc
    finally:
        connection.close()


def search_local_examples(db: Session, query: str) -> list[ApprovalExample]:
    global _cache_key, _cache_vectors
    allowed = {key: (title, content, outline) for key, title, content, outline in EXAMPLES}
    rows = [
        row
        for row in db.scalars(select(ApprovalExample)).all()
        if row.id in allowed and (row.title, row.content, row.outline) == allowed[row.id]
    ]
    if not rows:
        raise LocalSearchUnavailable("Examples not installed")
    rows.sort(key=lambda item: item.id)
    texts = [f"{row.title}\n{row.content}" for row in rows]
    key = hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode()).hexdigest()
    with _cache_lock:
        if _cache_key != key or _cache_vectors is None:
            _cache_vectors = _embed(texts)
            _cache_key = key
        vectors = _cache_vectors
    query_vector = _embed([query])[0]
    query_norm = math.sqrt(sum(x * x for x in query_vector))
    if not query_norm:
        raise LocalSearchUnavailable("Invalid local query")
    scores: list[tuple[float, ApprovalExample]] = []
    for row, vector in zip(rows, vectors, strict=True):
        norm = math.sqrt(sum(x * x for x in vector))
        if norm:
            score = sum(a * b for a, b in zip(query_vector, vector, strict=True)) / (
                query_norm * norm
            )
            if score >= 0.3:
                scores.append((score, row))
    scores.sort(key=lambda item: (-item[0], item[1].id))
    return [row for _, row in scores[:2]]

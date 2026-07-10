from __future__ import annotations

import heapq
from math import sqrt
from typing import Callable, Iterable, TypeVar

from unified_server.settings import get_settings

T = TypeVar("T")


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Stateless cosine similarity. Single pass: dot product and both norms
    are accumulated in one loop instead of three separate traversals."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = 0.0
    left_norm_sq = 0.0
    right_norm_sq = 0.0
    for a, b in zip(left, right):
        dot += a * b
        left_norm_sq += a * a
        right_norm_sq += b * b
    if left_norm_sq == 0.0 or right_norm_sq == 0.0:
        return 0.0
    return dot / sqrt(left_norm_sq * right_norm_sq)


def top_k_similar(
    query: list[float] | None,
    candidates: Iterable[tuple[T, list[float] | None]],
    k: int,
    min_score: float = 0.0,
) -> list[tuple[float, T]]:
    """Stateless top-k retrieval by cosine similarity against one query vector.

    Takes (item, embedding) pairs, skips unusable embeddings, and returns up to
    k (score, item) pairs sorted best-first. The query norm is computed once and
    a bounded heap keeps memory at O(k) however many candidates stream through.
    """
    if not query or k <= 0:
        return []
    query_norm_sq = 0.0
    for a in query:
        query_norm_sq += a * a
    if query_norm_sq == 0.0:
        return []

    dimensions = len(query)
    heap: list[tuple[float, int, T]] = []  # (score, tiebreak, item) — item never compared
    for index, (item, embedding) in enumerate(candidates):
        if not embedding or len(embedding) != dimensions:
            continue
        dot = 0.0
        candidate_norm_sq = 0.0
        for a, b in zip(query, embedding):
            dot += a * b
            candidate_norm_sq += b * b
        if candidate_norm_sq == 0.0:
            continue
        score = dot / sqrt(query_norm_sq * candidate_norm_sq)
        if score < min_score:
            continue
        if len(heap) < k:
            heapq.heappush(heap, (score, index, item))
        elif score > heap[0][0]:
            heapq.heapreplace(heap, (score, index, item))

    return [(score, item) for score, _, item in sorted(heap, key=lambda entry: entry[0], reverse=True)]


class EmbeddingService:
    """Embeds text via OpenAI; returns None (never raises) so chat keeps
    working when embeddings are unavailable."""

    def __init__(self, get_client: Callable[[], object | None]) -> None:
        self._get_client = get_client

    def embed(self, text: str) -> list[float] | None:
        client = self._get_client()
        if not client or not text.strip():
            return None
        try:
            response = client.embeddings.create(model=get_settings().OPENAI_EMBEDDING_MODEL, input=text)
            return list(response.data[0].embedding)
        except Exception:
            return None

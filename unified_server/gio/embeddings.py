from __future__ import annotations

from typing import Callable

from unified_server.settings import get_settings


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


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

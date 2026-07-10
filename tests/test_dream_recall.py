from __future__ import annotations

from unified_server.gio.embeddings import cosine_similarity, top_k_similar
from unified_server.gio.service import GioService
from unified_server.settings import get_settings

from tests.test_gio_context import FakeGioRepository, FakeProvider, FakeProviderRegistry


# --- stateless similarity utilities -----------------------------------------

def test_cosine_similarity_basic_geometry():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_cosine_similarity_rejects_unusable_vectors():
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_top_k_similar_returns_best_first_and_caps_at_k():
    query = [1.0, 0.0]
    candidates = [
        ("east", [1.0, 0.0]),        # score 1.0
        ("northeast", [1.0, 1.0]),   # ~0.707
        ("north", [0.0, 1.0]),       # 0.0
        ("near-east", [0.9, 0.1]),   # ~0.994
        ("west", [-1.0, 0.0]),       # -1.0
    ]

    results = top_k_similar(query, candidates, k=3)

    assert [item for _, item in results] == ["east", "near-east", "northeast"]
    assert results[0][0] == 1.0


def test_top_k_similar_applies_min_score_and_skips_bad_embeddings():
    query = [1.0, 0.0]
    candidates = [
        ("good", [1.0, 0.1]),
        ("orthogonal", [0.0, 1.0]),
        ("missing", None),
        ("wrong-dims", [1.0, 0.0, 0.0]),
        ("zero", [0.0, 0.0]),
    ]

    results = top_k_similar(query, candidates, k=5, min_score=0.5)

    assert [item for _, item in results] == ["good"]


def test_top_k_similar_handles_empty_query():
    assert top_k_similar(None, [("a", [1.0])], k=5) == []
    assert top_k_similar([], [("a", [1.0])], k=5) == []
    assert top_k_similar([1.0], [("a", [1.0])], k=0) == []


# --- associative dream recall during chat -----------------------------------

def _service_with_dreams() -> tuple[GioService, FakeGioRepository, FakeProvider]:
    repository = FakeGioRepository()
    provider = FakeProvider()
    service = GioService(repository=repository, providers=FakeProviderRegistry(provider))
    service.openai_client = None

    # Seven dreams; with query [1.0, 0.0] similarity decreases with the angle.
    for name, embedding in [
        ("aligned", [1.0, 0.0]),
        ("close", [0.95, 0.05]),
        ("near", [0.9, 0.2]),
        ("related", [0.7, 0.4]),
        ("loose", [0.6, 0.6]),
        ("distant", [0.1, 0.9]),
        ("orthogonal", [0.0, 1.0]),
    ]:
        repository.create_dream(
            conversation_id="conv-1",
            title=name,
            content=f"Reflection about {name}.",
            embedding=embedding,
        )
    return service, repository, provider


def test_chat_injects_five_most_similar_dreams(monkeypatch):
    service, _, provider = _service_with_dreams()
    monkeypatch.setattr(get_settings(), "GIO_DREAM_RECALL_PROBABILITY", 1.0)
    monkeypatch.setattr(get_settings(), "GIO_DREAM_RECALL_MIN_SCORE", 0.0)
    monkeypatch.setattr(service, "_embed", lambda text: [1.0, 0.0])

    service.chat_once("conv-1", "Thinking about alignment.", provider_name="openai", model="gpt-4.1-mini")

    system_blocks = [m["content"] for m in provider.calls[0]["messages"] if m["role"] == "system"]
    dream_blocks = [block for block in system_blocks if "Dream journal" in block]
    assert len(dream_blocks) == 1
    block = dream_blocks[0]
    for expected in ("aligned", "close", "near", "related", "loose"):
        assert expected in block
    assert "orthogonal" not in block
    assert "distant" not in block
    # Best match listed first.
    assert block.index("aligned") < block.index("close") < block.index("near")


def test_chat_skips_dream_recall_when_probability_zero(monkeypatch):
    service, _, provider = _service_with_dreams()
    monkeypatch.setattr(get_settings(), "GIO_DREAM_RECALL_PROBABILITY", 0.0)
    monkeypatch.setattr(service, "_embed", lambda text: [1.0, 0.0])

    service.chat_once("conv-1", "Thinking about alignment.", provider_name="openai", model="gpt-4.1-mini")

    system_blocks = [m["content"] for m in provider.calls[0]["messages"] if m["role"] == "system"]
    assert not any("Dream journal" in block for block in system_blocks)


def test_chat_skips_dream_recall_without_user_embedding(monkeypatch):
    service, _, provider = _service_with_dreams()
    monkeypatch.setattr(get_settings(), "GIO_DREAM_RECALL_PROBABILITY", 1.0)
    monkeypatch.setattr(service, "_embed", lambda text: None)

    service.chat_once("conv-1", "Thinking about alignment.", provider_name="openai", model="gpt-4.1-mini")

    system_blocks = [m["content"] for m in provider.calls[0]["messages"] if m["role"] == "system"]
    assert not any("Dream journal" in block for block in system_blocks)


def test_dream_recall_survives_missing_storage(monkeypatch):
    service, repository, provider = _service_with_dreams()
    monkeypatch.setattr(get_settings(), "GIO_DREAM_RECALL_PROBABILITY", 1.0)
    monkeypatch.setattr(service, "_embed", lambda text: [1.0, 0.0])

    def broken_list_dreams(conversation_id=None):
        raise RuntimeError("Dream Mode storage is missing.")

    monkeypatch.setattr(repository, "list_dreams", broken_list_dreams)

    result = service.chat_once("conv-1", "Still works.", provider_name="openai", model="gpt-4.1-mini")

    assert result["message"]["content"] == "refined response"
    system_blocks = [m["content"] for m in provider.calls[0]["messages"] if m["role"] == "system"]
    assert not any("Dream journal" in block for block in system_blocks)

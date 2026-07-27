from __future__ import annotations

from unified_server.gio.knowledge import GioKnowledgeService
from unified_server.gio.service import GioService
from unified_server.gio.tooling import GioContextSource, GioToolRouter
from unified_server.settings import get_settings
from tests.test_gio_context import FakeGioRepository, FakeProvider, FakeProviderRegistry


def test_gio_tool_router_detects_web_and_rag_hints():
    router = GioToolRouter()

    plan = router.plan("Search the web for the latest docs in the codebase")

    assert plan.use_web is True
    assert plan.use_rag is True
    assert plan.reasons


def test_gio_chat_injects_rag_and_web_context(monkeypatch):
    repository = FakeGioRepository()
    repository.add_message("conv-1", "assistant", "Recent answer one.", embedding=[1.0, 0.0])

    provider = FakeProvider(response_text="Use [R1] and [W1].")
    service = GioService(repository=repository, providers=FakeProviderRegistry(provider))
    service.openai_client = None

    monkeypatch.setattr(get_settings(), "GIO_TOOLS_ENABLED", True)
    monkeypatch.setattr(get_settings(), "GIO_KNOWLEDGE_ENABLED", True)
    monkeypatch.setattr(get_settings(), "GIO_WEB_SEARCH_ENABLED", True)
    monkeypatch.setattr(get_settings(), "GIO_DREAM_RECALL_ENABLED", False)
    monkeypatch.setattr(service, "_embed", lambda text: [1.0, 0.0])
    monkeypatch.setattr(
        service._knowledge,
        "search",
        lambda query, embedding: [
            GioContextSource(
                kind="rag",
                label="[R1]",
                title="README.md",
                source="README.md",
                snippet="Project docs say the server is Flask-based.",
            )
        ],
    )
    monkeypatch.setattr(
        service._web_search,
        "search",
        lambda query: [
            GioContextSource(
                kind="web",
                label="[W1]",
                title="Release notes",
                source="https://example.com/release-notes",
                url="https://example.com/release-notes",
                snippet="The latest release shipped this morning.",
            )
        ],
    )

    response = service.chat_once(
        "conv-1",
        "Search the web for the latest docs in the codebase",
        provider_name="openai",
        model="gpt-4.1-mini",
    )

    sent_messages = provider.calls[0]["messages"]
    joined = "\n\n".join(item["content"] for item in sent_messages if item["role"] == "system")
    assert "Retrieved project knowledge" in joined
    assert "Fresh web results" in joined
    assert "[R#]" in joined
    assert "[W#]" in joined
    assert "Project-evidence mode is active" in joined
    assert "Never invent filenames" in joined
    assert "README.md" in joined
    assert response["tooling"]["plan"]["use_rag"] is True
    assert response["tooling"]["plan"]["use_web"] is True
    assert len(response["tooling"]["sources"]) == 2


def test_gio_chat_warns_when_project_grounding_was_requested_but_no_sources_exist(monkeypatch):
    repository = FakeGioRepository()
    provider = FakeProvider(response_text="I do not have enough evidence.")
    service = GioService(repository=repository, providers=FakeProviderRegistry(provider))
    service.openai_client = None

    monkeypatch.setattr(get_settings(), "GIO_TOOLS_ENABLED", True)
    monkeypatch.setattr(get_settings(), "GIO_KNOWLEDGE_ENABLED", True)
    monkeypatch.setattr(get_settings(), "GIO_WEB_SEARCH_ENABLED", False)
    monkeypatch.setattr(get_settings(), "GIO_DREAM_RECALL_ENABLED", False)
    monkeypatch.setattr(service, "_embed", lambda text: [1.0, 0.0])
    monkeypatch.setattr(service._knowledge, "search", lambda query, embedding: [])

    service.chat_once(
        "conv-1",
        "Based on the codebase, how does Gio chat streaming work?",
        provider_name="openai",
        model="gpt-4.1-mini",
    )

    sent_messages = provider.calls[0]["messages"]
    joined = "\n\n".join(item["content"] for item in sent_messages if item["role"] == "system")
    assert "no reliable retrieved project context was found" in joined.lower()
    assert "do not infer missing filenames" in joined.lower()


class FakeKnowledgeRepository:
    def search_knowledge_chunks(self, query_embedding, *, top_k, min_score):
        return [
            {
                "chunk_id": "1",
                "document_id": "doc-1",
                "source_key": "unified_server/static/app.css",
                "title": "app.css",
                "content": "chat panel styles and layout",
                "score": 0.91,
                "tags": ["project"],
            },
            {
                "chunk_id": "2",
                "document_id": "doc-2",
                "source_key": "unified_server/web/gio.py",
                "title": "gio.py",
                "content": "route /api/gio/chat/stream returns NDJSON meta delta done events",
                "score": 0.74,
                "tags": ["project"],
            },
        ]

    def list_knowledge_documents(self, *, limit=500):
        return [
            {
                "id": "doc-3",
                "source_key": "unified_server/gio/tooling.py",
                "title": "tooling.py",
                "url": None,
                "tags": ["project"],
            }
        ]

    def get_knowledge_chunks_for_document(self, document_id, *, limit=3):
        return [
            {
                "id": "chunk-3",
                "document_id": document_id,
                "chunk_index": 0,
                "content": "class GioToolRouter plans when to use RAG and web search.",
            }
        ]


def test_gio_knowledge_reranks_code_hits_above_generic_matches(monkeypatch):
    monkeypatch.setattr(get_settings(), "GIO_KNOWLEDGE_TOP_K", 2)
    monkeypatch.setattr(get_settings(), "GIO_KNOWLEDGE_MIN_SCORE", 0.2)

    service = GioKnowledgeService(FakeKnowledgeRepository())
    sources = service.search("Based on the codebase, how does Gio chat streaming work?", [1.0, 0.0])

    assert sources[0].source == "unified_server/web/gio.py"
    assert sources[0].metadata["rerank_score"] > sources[1].metadata["rerank_score"]


def test_gio_knowledge_can_lexically_supplement_tooling_file(monkeypatch):
    monkeypatch.setattr(get_settings(), "GIO_KNOWLEDGE_TOP_K", 3)
    monkeypatch.setattr(get_settings(), "GIO_KNOWLEDGE_MIN_SCORE", 0.2)

    service = GioKnowledgeService(FakeKnowledgeRepository())
    sources = service.search("From the project files, where is the Gio tool routing logic implemented?", [1.0, 0.0])

    assert any(source.source == "unified_server/gio/tooling.py" for source in sources)

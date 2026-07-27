from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterator

from openai import OpenAI

from unified_server.core.conversations import require_conversation
from unified_server.gio.catalog import ModelCatalog, is_supported_gio_model, supports_reasoning
from unified_server.gio.chat import CONVERSATION_NOT_FOUND, GioChatOrchestrator, extract_reasoning_from_response
from unified_server.gio.dreams import DreamGenerator
from unified_server.gio.embeddings import EmbeddingService
from unified_server.gio.knowledge import GioKnowledgeService
from unified_server.gio.repository import GioMessage, GioSupabaseRepository
from unified_server.gio.tooling import GioToolRouter
from unified_server.gio.web_search import WebSearchService
from unified_server.gio.serialization import serialize_dream, serialize_message
from unified_server.gio.summaries import SummaryMaintainer
from unified_server.providers import ProviderRegistry
from unified_server.settings import get_settings


class GioService:
    """Facade over the Gio collaborators (chat, recall, summaries, dreams,
    catalog). Wires one repository and one OpenAI client into all of them and
    keeps the original public surface for the web layer and tests.

    The `openai_client`, `_embed`, `_summarize_messages`, and
    `_dream_from_sources` attributes are deliberate seams: collaborators reach
    them through callbacks, so swapping them on an instance affects every
    collaborator consistently.
    """

    def __init__(self, repository: GioSupabaseRepository | None = None, providers: ProviderRegistry | None = None) -> None:
        self.repository = repository or GioSupabaseRepository()
        self.providers = providers or ProviderRegistry()
        api_key = get_settings().OPENAI_API_KEY
        self.openai_client = OpenAI(api_key=api_key) if api_key else None

        get_client = lambda: self.openai_client  # noqa: E731 — late-bound so instance swaps propagate
        embed = lambda text: self._embed(text)  # noqa: E731

        self._embeddings = EmbeddingService(get_client)
        self._catalog = ModelCatalog(get_client)
        self._knowledge = GioKnowledgeService(self.repository)
        self._web_search = WebSearchService()
        self._tool_router = GioToolRouter()
        self._summaries = SummaryMaintainer(
            self.repository,
            get_client,
            embed=embed,
            summarize=lambda messages, previous_summary=None: self._summarize_messages(messages, previous_summary),
        )
        self._dreams = DreamGenerator(
            self.repository,
            get_client,
            embed=embed,
            dream_from_sources=lambda conversation_id, messages, latest_summary: self._dream_from_sources(
                conversation_id, messages, latest_summary
            ),
        )
        self._chat = GioChatOrchestrator(
            self.repository,
            self.providers,
            get_client,
            embed=embed,
            on_assistant_stored=lambda conversation_id: self._maybe_update_rolling_summary(conversation_id),
            recall_dreams=lambda query_embedding: self._recall_similar_dreams(query_embedding),
            knowledge_search=lambda query, query_embedding: self._knowledge.search(query, query_embedding),
            web_search=lambda query: self._web_search.search(query),
            tool_router=self._tool_router,
        )

    # -- schema / conversations -------------------------------------------------

    def ensure_schema(self) -> None:
        self.repository.ensure_schema()

    def list_conversations(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.repository.list_conversations()]

    def create_conversation(self, title: str = "New Chat") -> dict[str, Any]:
        return asdict(self.repository.create_conversation(title=title))

    def rename_conversation(self, conversation_id: str, title: str) -> dict[str, Any]:
        self._require_conversation(conversation_id)
        cleaned = " ".join((title or "").split()).strip()
        if not cleaned:
            raise ValueError("Title cannot be empty.")
        return asdict(self.repository.update_conversation_title(conversation_id, cleaned))

    def delete_conversation(self, conversation_id: str) -> None:
        self._require_conversation(conversation_id)
        self.repository.delete_conversation(conversation_id)

    def get_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        self._require_conversation(conversation_id)
        return [
            self.serialize_message(item)
            for item in self.repository.get_messages(conversation_id, include_embeddings=False)
            if item.role != "summary"
        ]

    # -- dreams -------------------------------------------------------------------

    def list_dreams(self, conversation_id: str | None = None) -> list[dict[str, Any]]:
        if conversation_id:
            self._require_conversation(conversation_id)
        return [self.serialize_dream(item) for item in self.repository.list_dreams(conversation_id)]

    def get_dream(self, dream_id: str) -> dict[str, Any]:
        dream = self.repository.get_dream((dream_id or "").strip())
        if not dream:
            raise ValueError("Dream not found.")
        return self.serialize_dream(dream)

    def create_dream(self, conversation_id: str) -> dict[str, Any]:
        self._require_conversation(conversation_id)
        return self.serialize_dream(self._dreams.create_dream(conversation_id))

    # -- models ---------------------------------------------------------------

    def list_models(self, provider_name: str | None = None) -> dict[str, Any]:
        return self._catalog.list_models()

    def list_openai_models(self) -> list[dict[str, Any]]:
        return self._catalog.list_openai_models()

    # -- chat -------------------------------------------------------------------

    def chat_once(
        self,
        conversation_id: str,
        user_text: str,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        return self._chat.chat_once(conversation_id, user_text, provider_name, model)

    def chat_stream(
        self,
        conversation_id: str,
        user_text: str,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        return self._chat.chat_stream(conversation_id, user_text, provider_name, model)

    # -- seams (collaborators call back through these) -----------------------

    def _embed(self, text: str) -> list[float] | None:
        return self._embeddings.embed(text)

    def _summarize_messages(self, messages: list[GioMessage], previous_summary: str | None = None) -> str | None:
        return self._summaries.summarize_messages(messages, previous_summary)

    def _dream_from_sources(
        self,
        conversation_id: str,
        messages: list[GioMessage],
        latest_summary: str | None,
    ) -> tuple[str, str]:
        return self._dreams.dream_from_sources(conversation_id, messages, latest_summary)

    def _maybe_update_rolling_summary(self, conversation_id: str) -> None:
        self._summaries.maybe_update_rolling_summary(conversation_id)

    def _recall_similar_dreams(self, query_embedding: list[float] | None):
        return self._dreams.recall_similar_dreams(query_embedding)

    def _extract_reasoning_from_response(self, response: Any) -> str | None:
        return extract_reasoning_from_response(response)

    def _require_conversation(self, conversation_id: str) -> None:
        require_conversation(self.repository, conversation_id, CONVERSATION_NOT_FOUND)

    _is_supported_gio_model = staticmethod(is_supported_gio_model)
    _supports_reasoning = staticmethod(supports_reasoning)
    serialize_message = staticmethod(serialize_message)
    serialize_dream = staticmethod(serialize_dream)

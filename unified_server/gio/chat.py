from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from unified_server.core.conversations import require_conversation
from unified_server.core.prompts import DEFAULT_SYSTEM_PROMPT
from unified_server.gio.heuristics import truncate_content
from unified_server.gio.recall import build_recall_block
from unified_server.gio.repository import GioDream, GioMessage, GioSupabaseRepository
from unified_server.gio.serialization import serialize_message
from unified_server.gio.tooling import (
    GioContextSource,
    GioToolPlan,
    GioToolRouter,
    build_citation_instruction,
    build_project_evidence_instruction,
    build_sources_block,
)
from unified_server.settings import get_settings

CONVERSATION_NOT_FOUND = "Conversation not found. Start a new chat or refresh the conversation list."


@dataclass(slots=True)
class PreparedChatTurn:
    provider_name: str
    model: str
    user_message: GioMessage
    messages: list[dict[str, str]]
    tool_plan: GioToolPlan
    sources: list[GioContextSource]


def clean_reasoning_text(text: str | None) -> str | None:
    cleaned = (text or "").strip()
    return cleaned or None


def extract_reasoning_from_response(response: Any) -> str | None:
    output_items = getattr(response, "output", None) or []
    chunks: list[str] = []
    for item in output_items:
        if getattr(item, "type", "") != "reasoning":
            continue
        summary = getattr(item, "summary", None) or []
        for part in summary:
            text = getattr(part, "text", "") or ""
            if text:
                chunks.append(text)
    return clean_reasoning_text("\n".join(chunks))


class GioChatOrchestrator:
    """Gio chat turns (sync + NDJSON streaming) over the Supabase repository."""

    def __init__(
        self,
        repository: GioSupabaseRepository,
        providers,
        get_client: Callable[[], object | None],
        *,
        embed: Callable[[str], list[float] | None],
        on_assistant_stored: Callable[[str], None],
        recall_dreams: Callable[[list[float] | None], list[tuple[float, GioDream]]] | None = None,
        knowledge_search: Callable[[str, list[float] | None], list[GioContextSource]] | None = None,
        web_search: Callable[[str], list[GioContextSource]] | None = None,
        tool_router: GioToolRouter | None = None,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self.repository = repository
        self.providers = providers
        self._get_client = get_client
        self._embed = embed
        self._on_assistant_stored = on_assistant_stored
        self._recall_dreams = recall_dreams
        self._knowledge_search = knowledge_search
        self._web_search = web_search
        self._tool_router = tool_router or GioToolRouter()
        self._rng = rng

    def chat_once(
        self,
        conversation_id: str,
        user_text: str,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        prepared = self._prepare_chat(
            conversation_id=conversation_id,
            user_text=user_text,
            provider_name=provider_name,
            model=model,
        )

        thinking_content = None
        client = self._get_client()
        if prepared.provider_name == "openai" and client:
            assistant_text, thinking_content = self._chat_openai(client, prepared.messages, prepared.model)
        else:
            provider = self.providers.get(prepared.provider_name)
            assistant_text = provider.chat(messages=prepared.messages, model=prepared.model)
        if not assistant_text:
            assistant_text = "No response generated."

        assistant_message = self._store_assistant_message(
            conversation_id=conversation_id,
            provider_name=prepared.provider_name,
            model=prepared.model,
            assistant_text=assistant_text,
            thinking_content=thinking_content,
        )
        return {
            "conversation_id": conversation_id,
            "user_message": serialize_message(prepared.user_message),
            "message": serialize_message(assistant_message),
            "tooling": self._serialize_tooling(prepared.tool_plan, prepared.sources),
        }

    def chat_stream(
        self,
        conversation_id: str,
        user_text: str,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        prepared = self._prepare_chat(
            conversation_id=conversation_id,
            user_text=user_text,
            provider_name=provider_name,
            model=model,
        )
        yield {
            "type": "meta",
            "conversation_id": conversation_id,
            "user_message": serialize_message(prepared.user_message),
            "tooling": self._serialize_tooling(prepared.tool_plan, prepared.sources),
        }

        if prepared.provider_name != "openai":
            provider = self.providers.get(prepared.provider_name)
            assistant_text = provider.chat(messages=prepared.messages, model=prepared.model)
            if not assistant_text:
                assistant_text = "No response generated."
            assistant_message = self._store_assistant_message(
                conversation_id=conversation_id,
                provider_name=prepared.provider_name,
                model=prepared.model,
                assistant_text=assistant_text,
                thinking_content=None,
            )
            yield {
                "type": "done",
                "conversation_id": conversation_id,
                "user_message": serialize_message(prepared.user_message),
                "message": serialize_message(assistant_message),
                "tooling": self._serialize_tooling(prepared.tool_plan, prepared.sources),
            }
            return

        client = self._get_client()
        if not client:
            raise ValueError("OPENAI_API_KEY is not set.")

        assistant_chunks: list[str] = []
        reasoning_chunks: list[str] = []
        with client.responses.stream(
            model=prepared.model,
            input=prepared.messages,
            store=False,
        ) as stream:
            for event in stream:
                event_type = getattr(event, "type", "")
                if event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", "") or ""
                    if delta:
                        assistant_chunks.append(delta)
                        yield {
                            "type": "delta",
                            "delta": delta,
                        }
                elif event_type.startswith("response.reasoning"):
                    delta = getattr(event, "delta", "") or getattr(event, "text", "") or ""
                    if delta:
                        reasoning_chunks.append(delta)

        assistant_text = "".join(assistant_chunks).strip() or "No response generated."
        assistant_message = self._store_assistant_message(
            conversation_id=conversation_id,
            provider_name=prepared.provider_name,
            model=prepared.model,
            assistant_text=assistant_text,
            thinking_content=clean_reasoning_text("".join(reasoning_chunks)),
        )
        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "user_message": serialize_message(prepared.user_message),
            "message": serialize_message(assistant_message),
            "tooling": self._serialize_tooling(prepared.tool_plan, prepared.sources),
        }

    def _prepare_chat(
        self,
        conversation_id: str,
        user_text: str,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> PreparedChatTurn:
        cleaned = user_text.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty.")

        require_conversation(self.repository, conversation_id, CONVERSATION_NOT_FOUND)
        settings = get_settings()
        provider_name = provider_name or settings.GIO_DEFAULT_PROVIDER
        model = model or settings.GIO_DEFAULT_MODEL
        user_embedding = self._embed(cleaned)
        user_message = self.repository.add_message(
            conversation_id=conversation_id,
            role="user",
            content=cleaned,
            provider=provider_name,
            model=model,
            embedding=user_embedding,
        )

        tool_plan, sources = self._collect_tool_context(cleaned, user_embedding)
        messages = self._build_prompt_context(conversation_id, user_embedding, tool_plan, sources)
        return PreparedChatTurn(
            provider_name=provider_name,
            model=model,
            user_message=user_message,
            messages=messages,
            tool_plan=tool_plan,
            sources=sources,
        )

    def _collect_tool_context(
        self,
        user_text: str,
        user_embedding: list[float] | None,
    ) -> tuple[GioToolPlan, list[GioContextSource]]:
        settings = get_settings()
        if not settings.GIO_TOOLS_ENABLED:
            return GioToolPlan(reasons=["Tools disabled in settings."]), []

        plan = self._tool_router.plan(user_text)
        sources: list[GioContextSource] = []

        if settings.GIO_KNOWLEDGE_ENABLED and plan.use_rag and self._knowledge_search:
            sources.extend(self._knowledge_search(user_text, user_embedding))

        if settings.GIO_WEB_SEARCH_ENABLED and plan.use_web and self._web_search:
            sources.extend(self._web_search(user_text))

        return plan, sources

    def _store_assistant_message(
        self,
        conversation_id: str,
        provider_name: str,
        model: str,
        assistant_text: str,
        thinking_content: str | None,
    ) -> GioMessage:
        assistant_embedding = self._embed(assistant_text)
        assistant_message = self.repository.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_text,
            provider=provider_name,
            model=model,
            thinking_content=thinking_content,
            embedding=assistant_embedding,
        )
        self._on_assistant_stored(conversation_id)
        return assistant_message

    @staticmethod
    def _chat_openai(client, messages: list[dict[str, str]], model: str) -> tuple[str, str | None]:
        response = client.responses.create(
            model=model,
            input=messages,
            store=False,
        )
        assistant_text = getattr(response, "output_text", "").strip()
        reasoning_content = extract_reasoning_from_response(response)
        return assistant_text, reasoning_content

    def _build_prompt_context(
        self,
        conversation_id: str,
        user_embedding: list[float] | None,
        tool_plan: GioToolPlan,
        sources: list[GioContextSource],
    ) -> list[dict[str, str]]:
        all_messages = self.repository.get_messages(conversation_id)
        latest_summary = self.repository.get_latest_summary(conversation_id)
        conversation_messages = [item for item in all_messages if item.role in {"user", "assistant", "system"}]
        recent_messages = conversation_messages[-get_settings().GIO_RECENT_MESSAGES_LIMIT:]

        prompt_messages = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}]
        if latest_summary and latest_summary.content.strip():
            prompt_messages.append(
                {
                    "role": "system",
                    "content": "Rolling summary of earlier conversation context. Use it as background, but defer to the recent direct messages when they conflict.\n"
                    + latest_summary.content,
                }
            )

        recall_block = build_recall_block(conversation_messages, recent_messages, user_embedding)
        if recall_block:
            prompt_messages.append({"role": "system", "content": recall_block})

        rag_sources = [item for item in sources if item.kind == "rag"]
        web_sources = [item for item in sources if item.kind == "web"]
        project_evidence_instruction = build_project_evidence_instruction(tool_plan, rag_sources)
        if project_evidence_instruction:
            prompt_messages.append({"role": "system", "content": project_evidence_instruction})
        rag_block = build_sources_block(
            "Retrieved project knowledge",
            "Use these retrieved snippets when they help. Prefer them over guesses about the project, files, or stored notes. When answering codebase questions, quote exact paths or identifiers from here when available.",
            rag_sources,
        )
        if rag_block:
            prompt_messages.append({"role": "system", "content": rag_block})

        web_block = build_sources_block(
            "Fresh web results",
            "Use these only for current or external facts. If they conflict or look thin, say so plainly.",
            web_sources,
        )
        if web_block:
            prompt_messages.append({"role": "system", "content": web_block})

        citation_instruction = build_citation_instruction(bool(rag_sources), bool(web_sources))
        if citation_instruction:
            prompt_messages.append({"role": "system", "content": citation_instruction})

        dream_block = self._build_dream_reflection_block(user_embedding)
        if dream_block:
            prompt_messages.append({"role": "system", "content": dream_block})

        prompt_messages.extend({"role": item.role, "content": item.content} for item in recent_messages)
        return prompt_messages

    def _build_dream_reflection_block(self, user_embedding: list[float] | None) -> str | None:
        """Occasional associative reflection: with configured probability, pull
        the dreams most similar to the current thought process and surface them
        as the assistant's own remembered impressions."""
        settings = get_settings()
        if not settings.GIO_DREAM_RECALL_ENABLED or not self._recall_dreams or not user_embedding:
            return None
        if not self._rng() < settings.GIO_DREAM_RECALL_PROBABILITY:
            return None

        scored_dreams = self._recall_dreams(user_embedding)
        if not scored_dreams:
            return None

        lines = [
            "Recalled reflections from your Dream journal — your own past private thinking, not user messages.",
            "They surfaced because they resemble the current topic. Draw on them only when they genuinely help; never quote them verbatim or present them as something the user said.",
        ]
        for _, dream in scored_dreams:
            date = (dream.updated_at or dream.created_at or "")[:10]
            lines.append(f"- [{date}] {dream.title}: {truncate_content(dream.content, limit=300)}")
        return "\n".join(lines)

    @staticmethod
    def _serialize_tooling(plan: GioToolPlan, sources: list[GioContextSource]) -> dict[str, Any]:
        return {
            "plan": plan.to_dict(),
            "sources": [item.to_dict() for item in sources],
        }

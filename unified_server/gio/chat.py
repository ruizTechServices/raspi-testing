from __future__ import annotations

from typing import Any, Callable, Iterator

from unified_server.core.conversations import require_conversation
from unified_server.core.prompts import DEFAULT_SYSTEM_PROMPT
from unified_server.gio.recall import build_recall_block
from unified_server.gio.repository import GioMessage, GioSupabaseRepository
from unified_server.gio.serialization import serialize_message
from unified_server.settings import get_settings

CONVERSATION_NOT_FOUND = "Conversation not found. Start a new chat or refresh the conversation list."


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
    ) -> None:
        self.repository = repository
        self.providers = providers
        self._get_client = get_client
        self._embed = embed
        self._on_assistant_stored = on_assistant_stored

    def chat_once(
        self,
        conversation_id: str,
        user_text: str,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        provider_name, model, user_message, messages = self._prepare_chat(
            conversation_id=conversation_id,
            user_text=user_text,
            provider_name=provider_name,
            model=model,
        )

        thinking_content = None
        client = self._get_client()
        if provider_name == "openai" and client:
            assistant_text, thinking_content = self._chat_openai(client, messages, model)
        else:
            provider = self.providers.get(provider_name)
            assistant_text = provider.chat(messages=messages, model=model)
        if not assistant_text:
            assistant_text = "No response generated."

        assistant_message = self._store_assistant_message(
            conversation_id=conversation_id,
            provider_name=provider_name,
            model=model,
            assistant_text=assistant_text,
            thinking_content=thinking_content,
        )
        return {
            "conversation_id": conversation_id,
            "user_message": serialize_message(user_message),
            "message": serialize_message(assistant_message),
        }

    def chat_stream(
        self,
        conversation_id: str,
        user_text: str,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        provider_name, model, user_message, messages = self._prepare_chat(
            conversation_id=conversation_id,
            user_text=user_text,
            provider_name=provider_name,
            model=model,
        )
        yield {
            "type": "meta",
            "conversation_id": conversation_id,
            "user_message": serialize_message(user_message),
        }

        if provider_name != "openai":
            provider = self.providers.get(provider_name)
            assistant_text = provider.chat(messages=messages, model=model)
            if not assistant_text:
                assistant_text = "No response generated."
            assistant_message = self._store_assistant_message(
                conversation_id=conversation_id,
                provider_name=provider_name,
                model=model,
                assistant_text=assistant_text,
                thinking_content=None,
            )
            yield {
                "type": "done",
                "conversation_id": conversation_id,
                "user_message": serialize_message(user_message),
                "message": serialize_message(assistant_message),
            }
            return

        client = self._get_client()
        if not client:
            raise ValueError("OPENAI_API_KEY is not set.")

        assistant_chunks: list[str] = []
        reasoning_chunks: list[str] = []
        with client.responses.stream(
            model=model,
            input=messages,
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
            provider_name=provider_name,
            model=model,
            assistant_text=assistant_text,
            thinking_content=clean_reasoning_text("".join(reasoning_chunks)),
        )
        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "user_message": serialize_message(user_message),
            "message": serialize_message(assistant_message),
        }

    def _prepare_chat(
        self,
        conversation_id: str,
        user_text: str,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> tuple[str, str, GioMessage, list[dict[str, str]]]:
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

        messages = self._build_prompt_context(conversation_id, user_embedding)
        return provider_name, model, user_message, messages

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

        prompt_messages.extend({"role": item.role, "content": item.content} for item in recent_messages)
        return prompt_messages

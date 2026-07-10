from __future__ import annotations

from dataclasses import asdict

from unified_server.memory import MemoryService
from unified_server.providers import ProviderRegistry
from unified_server.repository import SQLiteRepository
from unified_server.settings import get_settings


DEFAULT_SYSTEM_PROMPT = (
    "You are a practical AI assistant running on a Raspberry Pi. "
    "Be clear, direct, and useful. Prefer pragmatic solutions over overengineering."
)


class ChatService:
    def __init__(self) -> None:
        self.repository = SQLiteRepository()
        self.providers = ProviderRegistry()
        self.memory = MemoryService(self.repository)

    def list_conversations(self):
        return self.repository.list_conversations()

    def create_conversation(self, title: str = "New Chat") -> str:
        return self.repository.create_conversation(title=title)

    def get_messages(self, conversation_id: str):
        self._require_conversation(conversation_id)
        return self.repository.get_messages(conversation_id)

    def rename_conversation(self, conversation_id: str, title: str) -> dict:
        self._require_conversation(conversation_id)
        cleaned = " ".join((title or "").split()).strip()
        if not cleaned:
            raise ValueError("Title cannot be empty.")
        return asdict(self.repository.update_conversation_title(conversation_id, cleaned))

    def delete_conversation(self, conversation_id: str) -> None:
        self._require_conversation(conversation_id)
        self.repository.delete_conversation(conversation_id)

    def chat(self, conversation_id: str, user_text: str, provider_name: str | None = None, model: str | None = None) -> dict:
        cleaned = user_text.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty.")

        self._require_conversation(conversation_id)

        settings = get_settings()
        provider_name = provider_name or settings.DEFAULT_PROVIDER
        model = model or settings.DEFAULT_MODEL

        self.repository.add_message(
            conversation_id=conversation_id,
            role="user",
            content=cleaned,
            provider=provider_name,
            model=model,
        )

        memory_block = self.memory.build_memory_block(conversation_id)
        messages = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}]
        if memory_block:
            messages.append({"role": "system", "content": memory_block})
        messages.extend(self.repository.get_messages_for_llm(conversation_id))

        provider = self.providers.get(provider_name)
        assistant_text = provider.chat(messages=messages, model=model)
        if not assistant_text:
            assistant_text = "No response generated."

        message_id = self.repository.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_text,
            provider=provider_name,
            model=model,
        )
        self.memory.remember_turn(conversation_id, cleaned, assistant_text)

        return {
            "conversation_id": conversation_id,
            "message": {
                "id": message_id,
                "role": "assistant",
                "content": assistant_text,
                "provider": provider_name,
                "model": model,
            },
        }

    def _require_conversation(self, conversation_id: str) -> None:
        cleaned = (conversation_id or "").strip()
        if not cleaned:
            raise ValueError("conversation_id is required.")
        if not self.repository.conversation_exists(cleaned):
            raise ValueError("Conversation not found.")

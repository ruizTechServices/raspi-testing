from __future__ import annotations

from dataclasses import asdict

from unified_server.chat.memory import CHAT_PROFILE, MemoryService
from unified_server.chat.repository import SQLiteRepository
from unified_server.core.chat_engine import run_chat_turn
from unified_server.core.conversations import require_conversation
from unified_server.core.prompts import DEFAULT_SYSTEM_PROMPT
from unified_server.providers import ProviderRegistry


class ChatService:
    def __init__(
        self,
        repository: SQLiteRepository | None = None,
        providers: ProviderRegistry | None = None,
        memory: MemoryService | None = None,
    ) -> None:
        self.repository = repository or SQLiteRepository()
        self.providers = providers or ProviderRegistry()
        self.memory = memory or MemoryService(self.repository, CHAT_PROFILE)

    def list_conversations(self):
        return self.repository.list_conversations()

    def create_conversation(self, title: str = "New Chat") -> str:
        return self.repository.create_conversation(title=title)

    def get_messages(self, conversation_id: str):
        require_conversation(self.repository, conversation_id)
        return self.repository.get_messages(conversation_id)

    def rename_conversation(self, conversation_id: str, title: str) -> dict:
        require_conversation(self.repository, conversation_id)
        cleaned = " ".join((title or "").split()).strip()
        if not cleaned:
            raise ValueError("Title cannot be empty.")
        return asdict(self.repository.update_conversation_title(conversation_id, cleaned))

    def delete_conversation(self, conversation_id: str) -> None:
        require_conversation(self.repository, conversation_id)
        self.repository.delete_conversation(conversation_id)

    def chat(self, conversation_id: str, user_text: str, provider_name: str | None = None, model: str | None = None) -> dict:
        cleaned = user_text.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty.")

        require_conversation(self.repository, conversation_id)

        result = run_chat_turn(
            repository=self.repository,
            providers=self.providers,
            conversation_id=conversation_id,
            user_text=cleaned,
            provider_name=provider_name,
            model=model,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            build_memory_block=lambda: self.memory.build_memory_block(conversation_id),
        )
        self.memory.remember_turn(conversation_id, cleaned, result["message"]["content"])
        return result

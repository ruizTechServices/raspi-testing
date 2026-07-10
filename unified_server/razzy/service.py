from __future__ import annotations

from unified_server.chat.memory import RAZZY_PROFILE, MemoryService
from unified_server.chat.repository import SQLiteRepository
from unified_server.core.chat_engine import run_chat_turn
from unified_server.core.conversations import require_conversation
from unified_server.providers import ProviderRegistry
from unified_server.razzy.identity import DEFAULT_RAZZY_SYSTEM_PROMPT, RAZZY_IDENTITY


class RazzyService:
    def __init__(self, repository: SQLiteRepository | None = None, providers: ProviderRegistry | None = None) -> None:
        self.repository = repository or SQLiteRepository()
        self.providers = providers or ProviderRegistry()
        self.memory = MemoryService(self.repository, RAZZY_PROFILE)

    def profile(self) -> dict:
        return RAZZY_IDENTITY

    def create_session(self, title: str = "Razzy Chat") -> str:
        return self.repository.create_conversation(title=title)

    def list_sessions(self):
        return self.repository.list_conversations()

    def get_messages(self, conversation_id: str):
        return self.repository.get_messages(conversation_id)

    def remember(self, conversation_id: str, content: str, cell_type: str = "fact", salience: float = 0.8) -> int:
        if not content.strip():
            raise ValueError("Memory content cannot be empty.")
        return self.memory.remember(conversation_id, content, cell_type, salience)

    def recall(self, conversation_id: str, limit: int = 10) -> list[dict]:
        return self.memory.recall(conversation_id, limit=limit)

    def chat(self, conversation_id: str, user_text: str, provider_name: str | None = None, model: str | None = None) -> dict:
        cleaned = user_text.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty.")

        require_conversation(self.repository, conversation_id)

        return run_chat_turn(
            repository=self.repository,
            providers=self.providers,
            conversation_id=conversation_id,
            user_text=cleaned,
            provider_name=provider_name,
            model=model,
            system_prompt=DEFAULT_RAZZY_SYSTEM_PROMPT,
            build_memory_block=lambda: self.memory.build_memory_block(conversation_id),
        )

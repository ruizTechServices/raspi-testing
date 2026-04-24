from __future__ import annotations

from unified_server.config import DEFAULT_MODEL, DEFAULT_PROVIDER
from unified_server.providers import ProviderRegistry
from unified_server.razzy_identity import DEFAULT_RAZZY_SYSTEM_PROMPT, RAZZY_IDENTITY
from unified_server.razzy_memory import RazzyMemoryService
from unified_server.repository import SQLiteRepository


class RazzyService:
    def __init__(self, repository: SQLiteRepository | None = None, providers: ProviderRegistry | None = None) -> None:
        self.repository = repository or SQLiteRepository()
        self.providers = providers or ProviderRegistry()
        self.memory = RazzyMemoryService(self.repository)

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

        provider_name = provider_name or DEFAULT_PROVIDER
        model = model or DEFAULT_MODEL

        self.repository.add_message(
            conversation_id=conversation_id,
            role="user",
            content=cleaned,
            provider=provider_name,
            model=model,
        )

        messages = [{"role": "system", "content": DEFAULT_RAZZY_SYSTEM_PROMPT}]
        memory_block = self.memory.build_context_block(conversation_id)
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

from __future__ import annotations

from unified_server.repository import SQLiteRepository
from unified_server.settings import get_settings


class MemoryService:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    def build_memory_block(self, conversation_id: str) -> str:
        settings = get_settings()
        if not settings.ENABLE_MEMORY:
            return ""
        cells = self.repository.get_top_memory(conversation_id=conversation_id, limit=settings.MEMORY_TOP_K)
        if not cells:
            return ""
        lines = [f"- [{cell.cell_type}] {cell.content}" for cell in cells]
        return "Relevant memory:\n" + "\n".join(lines)

    def remember_turn(self, conversation_id: str, user_text: str, assistant_text: str) -> None:
        if not get_settings().ENABLE_MEMORY:
            return
        user_clean = user_text.strip()
        assistant_clean = assistant_text.strip()
        if user_clean:
            self.repository.add_memory_cell(conversation_id, "task", user_clean[:500], 0.6)
        if assistant_clean:
            self.repository.add_memory_cell(conversation_id, "summary", assistant_clean[:500], 0.4)

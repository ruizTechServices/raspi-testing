from __future__ import annotations

from dataclasses import asdict

from unified_server.repository import SQLiteRepository


class RazzyMemoryService:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    def remember(self, conversation_id: str, content: str, cell_type: str = "fact", salience: float = 0.8) -> int:
        return self.repository.add_memory_cell(
            conversation_id=conversation_id,
            cell_type=cell_type,
            content=content.strip(),
            salience=salience,
        )

    def recall(self, conversation_id: str, limit: int = 10) -> list[dict]:
        cells = self.repository.get_top_memory(conversation_id=conversation_id, limit=limit)
        return [asdict(cell) for cell in cells]

    def build_context_block(self, conversation_id: str, limit: int = 8) -> str:
        cells = self.repository.get_top_memory(conversation_id=conversation_id, limit=limit)
        if not cells:
            return ""
        lines = [f"- [{cell.cell_type}] {cell.content}" for cell in cells]
        return "Razzy memory about Gio and this conversation:\n" + "\n".join(lines)

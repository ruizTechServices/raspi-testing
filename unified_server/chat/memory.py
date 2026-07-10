from __future__ import annotations

from dataclasses import asdict, dataclass

from unified_server.chat.repository import SQLiteRepository
from unified_server.settings import get_settings

TURN_CONTENT_LIMIT = 500


@dataclass(frozen=True)
class MemoryProfile:
    """Personality-specific memory behavior over the shared memory_cells table."""

    header: str
    gated_by_enable_memory: bool
    recall_limit: int | None  # None -> settings.MEMORY_TOP_K at call time
    remember_default_salience: float
    turn_task_salience: float
    turn_summary_salience: float


CHAT_PROFILE = MemoryProfile(
    header="Relevant memory:",
    gated_by_enable_memory=True,
    recall_limit=None,
    remember_default_salience=0.5,
    turn_task_salience=0.6,
    turn_summary_salience=0.4,
)

RAZZY_PROFILE = MemoryProfile(
    header="Razzy memory about Gio and this conversation:",
    gated_by_enable_memory=False,
    recall_limit=8,
    remember_default_salience=0.8,
    turn_task_salience=0.6,
    turn_summary_salience=0.4,
)


class MemoryService:
    def __init__(self, repository: SQLiteRepository, profile: MemoryProfile = CHAT_PROFILE) -> None:
        self.repository = repository
        self.profile = profile

    def build_memory_block(self, conversation_id: str) -> str:
        if self.profile.gated_by_enable_memory and not get_settings().ENABLE_MEMORY:
            return ""
        limit = self.profile.recall_limit or get_settings().MEMORY_TOP_K
        cells = self.repository.get_top_memory(conversation_id=conversation_id, limit=limit)
        if not cells:
            return ""
        lines = [f"- [{cell.cell_type}] {cell.content}" for cell in cells]
        return self.profile.header + "\n" + "\n".join(lines)

    def remember(self, conversation_id: str, content: str, cell_type: str = "fact", salience: float | None = None) -> int:
        return self.repository.add_memory_cell(
            conversation_id=conversation_id,
            cell_type=cell_type,
            content=content.strip(),
            salience=salience if salience is not None else self.profile.remember_default_salience,
        )

    def recall(self, conversation_id: str, limit: int = 10) -> list[dict]:
        cells = self.repository.get_top_memory(conversation_id=conversation_id, limit=limit)
        return [asdict(cell) for cell in cells]

    def remember_turn(self, conversation_id: str, user_text: str, assistant_text: str) -> None:
        if self.profile.gated_by_enable_memory and not get_settings().ENABLE_MEMORY:
            return
        user_clean = user_text.strip()
        assistant_clean = assistant_text.strip()
        if user_clean:
            self.repository.add_memory_cell(
                conversation_id, "task", user_clean[:TURN_CONTENT_LIMIT], self.profile.turn_task_salience
            )
        if assistant_clean:
            self.repository.add_memory_cell(
                conversation_id, "summary", assistant_clean[:TURN_CONTENT_LIMIT], self.profile.turn_summary_salience
            )

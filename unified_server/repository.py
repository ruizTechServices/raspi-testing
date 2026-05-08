from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from unified_server.database import get_connection
from unified_server.models import ChatMessage, Conversation, MemoryCell


class SQLiteRepository:
    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_conversation(self, title: str = "New Chat") -> str:
        conversation_id = str(uuid4())
        now = self._utc_now()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conversation_id, title, now, now),
            )
            conn.commit()
        return conversation_id

    def list_conversations(self) -> list[Conversation]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
            ).fetchall()
        return [Conversation(**dict(row)) for row in rows]

    def conversation_exists(self, conversation_id: str) -> bool:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        return row is not None

    def update_conversation_title(self, conversation_id: str, title: str) -> Conversation:
        now = self._utc_now()
        with get_connection() as conn:
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, conversation_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        if not row:
            raise ValueError("Conversation not found.")
        return Conversation(**dict(row))

    def delete_conversation(self, conversation_id: str) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()

    def get_messages(self, conversation_id: str) -> list[ChatMessage]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, conversation_id, role, content, provider, model, created_at FROM messages WHERE conversation_id = ? ORDER BY id ASC",
                (conversation_id,),
            ).fetchall()
        return [ChatMessage(**dict(row)) for row in rows]

    def add_message(self, conversation_id: str, role: str, content: str, provider: str | None = None, model: str | None = None) -> int:
        now = self._utc_now()
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO messages (conversation_id, role, provider, model, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, role, provider, model, content, now),
            )
            conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
            current = conn.execute("SELECT title FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            if current and current['title'] == 'New Chat' and role == 'user':
                title = " ".join(content.strip().split())[:60]
                if len(content.strip()) > 60:
                    title += '...'
                if title:
                    conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
            conn.commit()
            return int(cursor.lastrowid)

    def add_memory_cell(self, conversation_id: str, cell_type: str, content: str, salience: float = 0.5) -> int:
        now = self._utc_now()
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO memory_cells (conversation_id, cell_type, content, salience, created_at) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, cell_type, content, salience, now),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_top_memory(self, conversation_id: str, limit: int = 5) -> list[MemoryCell]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, conversation_id, cell_type, content, salience, created_at FROM memory_cells WHERE conversation_id = ? ORDER BY salience DESC, id DESC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
        return [MemoryCell(**dict(row)) for row in rows]

    def get_messages_for_llm(self, conversation_id: str) -> list[dict[str, str]]:
        messages = self.get_messages(conversation_id)
        return [{"role": item.role, "content": item.content} for item in messages if item.role in {"system", "user", "assistant"}]

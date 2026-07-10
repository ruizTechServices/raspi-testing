from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from unified_server.settings import get_settings
from unified_server.supabase_client import SupabaseRequestError, SupabaseRestClient


@dataclass(slots=True)
class GioConversation:
    id: str
    title: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class GioMessage:
    id: str
    conversation_id: str
    role: str
    content: str
    provider: str | None
    model: str | None
    thinking_content: str | None
    embedding: list[float] | None
    created_at: str


@dataclass(slots=True)
class GioSummary:
    id: str
    conversation_id: str
    content: str
    model: str | None
    embedding: list[float] | None
    created_at: str
    updated_at: str


@dataclass(slots=True)
class GioDream:
    id: str
    conversation_id: str
    title: str
    content: str
    model: str | None
    source_message_ids: list[str]
    embedding: list[float] | None
    created_at: str
    updated_at: str


class GioSupabaseRepository:
    def __init__(self, client: SupabaseRestClient | None = None) -> None:
        self.client = client or SupabaseRestClient()
        settings = get_settings()
        self.conversations_table = settings.GIO_CONVERSATIONS_TABLE
        self.messages_table = settings.GIO_MESSAGES_TABLE
        self.summaries_table = settings.GIO_SUMMARIES_TABLE
        self.dreams_table = settings.GIO_DREAMS_TABLE
        self._summary_table_available: bool | None = None
        self._dream_table_available: bool | None = None

    def ensure_schema(self) -> None:
        try:
            self.client.select(
                self.conversations_table,
                query={"select": "id", "limit": "1"},
            )
            self.client.select(
                self.messages_table,
                query={"select": "id", "limit": "1"},
            )
            self._summary_table_available = self._detect_summary_table()
            self._dream_table_available = self._detect_dream_table()
        except SupabaseRequestError as exc:
            raise RuntimeError(
                "Supabase schema is missing. Create tables `gio_conversations` and `gio_messages` in the Supabase SQL Editor first."
            ) from exc

    def create_conversation(self, title: str = "New Chat") -> GioConversation:
        conversation_id = str(uuid4())
        now = self._utc_now()
        rows = self.client.insert(
            self.conversations_table,
            {"id": conversation_id, "title": title, "created_at": now, "updated_at": now},
        )
        return self._conversation_from_row(rows[0])

    def list_conversations(self) -> list[GioConversation]:
        rows = self.client.select(
            self.conversations_table,
            query={"select": "id,title,created_at,updated_at", "order": "updated_at.desc"},
        )
        return [self._conversation_from_row(row) for row in rows]

    def conversation_exists(self, conversation_id: str) -> bool:
        rows = self.client.select(
            self.conversations_table,
            query={"select": "id", "id": f"eq.{conversation_id}", "limit": "1"},
        )
        return bool(rows)

    def update_conversation_title(self, conversation_id: str, title: str) -> GioConversation:
        rows = self.client.update(
            self.conversations_table,
            {"title": title, "updated_at": self._utc_now()},
            query={"id": f"eq.{conversation_id}"},
        )
        if not rows:
            raise ValueError("Conversation not found.")
        return self._conversation_from_row(rows[0])

    def delete_conversation(self, conversation_id: str) -> None:
        self.client.delete(
            self.conversations_table,
            query={"id": f"eq.{conversation_id}"},
            returning="minimal",
        )

    def get_messages(self, conversation_id: str) -> list[GioMessage]:
        rows = self.client.select(
            self.messages_table,
            query={
                "select": "id,conversation_id,role,content,provider,model,thinking_content,embedding,created_at",
                "conversation_id": f"eq.{conversation_id}",
                "order": "created_at.asc",
            },
        )
        return [self._message_from_row(row) for row in rows]

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        provider: str | None = None,
        model: str | None = None,
        thinking_content: str | None = None,
        embedding: list[float] | None = None,
    ) -> GioMessage:
        message_id = str(uuid4())
        now = self._utc_now()
        rows = self.client.insert(
            self.messages_table,
            {
                "id": message_id,
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "provider": provider,
                "model": model,
                "thinking_content": thinking_content,
                "embedding": embedding,
                "created_at": now,
            },
        )
        self.client.update(
            self.conversations_table,
            {"updated_at": now},
            query={"id": f"eq.{conversation_id}"},
            returning="minimal",
        )
        self._maybe_title_conversation(conversation_id, role, content)
        return self._message_from_row(rows[0])

    def get_latest_summary(self, conversation_id: str) -> GioSummary | None:
        if self._summary_storage_available():
            rows = self.client.select(
                self.summaries_table,
                query={
                    "select": "id,conversation_id,content,model,embedding,created_at,updated_at",
                    "conversation_id": f"eq.{conversation_id}",
                    "order": "updated_at.desc",
                    "limit": "1",
                },
            )
            if rows:
                return self._summary_from_row(rows[0])

        summary_messages = [item for item in self.get_messages(conversation_id) if item.role == "summary"]
        if not summary_messages:
            return None
        latest = summary_messages[-1]
        return GioSummary(
            id=latest.id,
            conversation_id=latest.conversation_id,
            content=latest.content,
            model=latest.model,
            embedding=latest.embedding,
            created_at=latest.created_at,
            updated_at=latest.created_at,
        )

    def save_summary(
        self,
        conversation_id: str,
        content: str,
        model: str | None = None,
        embedding: list[float] | None = None,
    ) -> GioSummary:
        now = self._utc_now()
        existing = self.get_latest_summary(conversation_id)

        if self._summary_storage_available():
            if existing and self._is_summary_row_in_table(existing.id):
                rows = self.client.update(
                    self.summaries_table,
                    {"content": content, "model": model, "embedding": embedding, "updated_at": now},
                    query={"id": f"eq.{existing.id}"},
                )
                return self._summary_from_row(rows[0])

            summary_id = str(uuid4())
            rows = self.client.insert(
                self.summaries_table,
                {
                    "id": summary_id,
                    "conversation_id": conversation_id,
                    "content": content,
                    "model": model,
                    "embedding": embedding,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            return self._summary_from_row(rows[0])

        summary_message = self.add_message(
            conversation_id=conversation_id,
            role="summary",
            content=content,
            provider="openai",
            model=model,
            thinking_content=None,
            embedding=embedding,
        )
        return GioSummary(
            id=summary_message.id,
            conversation_id=summary_message.conversation_id,
            content=summary_message.content,
            model=summary_message.model,
            embedding=summary_message.embedding,
            created_at=summary_message.created_at,
            updated_at=summary_message.created_at,
        )

    def list_dreams(self, conversation_id: str | None = None) -> list[GioDream]:
        if not self._dream_storage_available():
            raise RuntimeError(
                "Dream Mode storage is missing. Apply the Supabase schema for `gio_dream_entries` first."
            )
        query = {
            "select": "id,conversation_id,title,content,model,source_message_ids,embedding,created_at,updated_at",
            "order": "updated_at.desc",
        }
        if conversation_id:
            query["conversation_id"] = f"eq.{conversation_id}"
        rows = self.client.select(self.dreams_table, query=query)
        return [self._dream_from_row(row) for row in rows]

    def get_dream(self, dream_id: str) -> GioDream | None:
        if not self._dream_storage_available():
            raise RuntimeError(
                "Dream Mode storage is missing. Apply the Supabase schema for `gio_dream_entries` first."
            )
        rows = self.client.select(
            self.dreams_table,
            query={
                "select": "id,conversation_id,title,content,model,source_message_ids,embedding,created_at,updated_at",
                "id": f"eq.{dream_id}",
                "limit": "1",
            },
        )
        if not rows:
            return None
        return self._dream_from_row(rows[0])

    def create_dream(
        self,
        conversation_id: str,
        title: str,
        content: str,
        model: str | None = None,
        source_message_ids: list[str] | None = None,
        embedding: list[float] | None = None,
    ) -> GioDream:
        if not self._dream_storage_available():
            raise RuntimeError(
                "Dream Mode storage is missing. Apply the Supabase schema for `gio_dream_entries` first."
            )
        dream_id = str(uuid4())
        now = self._utc_now()
        rows = self.client.insert(
            self.dreams_table,
            {
                "id": dream_id,
                "conversation_id": conversation_id,
                "title": title,
                "content": content,
                "model": model,
                "source_message_ids": source_message_ids or [],
                "embedding": embedding,
                "created_at": now,
                "updated_at": now,
            },
        )
        self.client.update(
            self.conversations_table,
            {"updated_at": now},
            query={"id": f"eq.{conversation_id}"},
            returning="minimal",
        )
        return self._dream_from_row(rows[0])

    def get_messages_for_llm(self, conversation_id: str) -> list[dict[str, str]]:
        messages = self.get_messages(conversation_id)
        return [{"role": item.role, "content": item.content} for item in messages if item.role in {"user", "assistant", "system"}]

    def _summary_storage_available(self) -> bool:
        if self._summary_table_available is None:
            self._summary_table_available = self._detect_summary_table()
        return self._summary_table_available

    def _detect_summary_table(self) -> bool:
        try:
            self.client.select(
                self.summaries_table,
                query={"select": "id", "limit": "1"},
            )
            return True
        except SupabaseRequestError:
            return False

    def _dream_storage_available(self) -> bool:
        if self._dream_table_available is None:
            self._dream_table_available = self._detect_dream_table()
        return self._dream_table_available

    def _detect_dream_table(self) -> bool:
        try:
            self.client.select(
                self.dreams_table,
                query={"select": "id", "limit": "1"},
            )
            return True
        except SupabaseRequestError:
            return False

    def _is_summary_row_in_table(self, summary_id: str) -> bool:
        if not self._summary_storage_available():
            return False
        try:
            rows = self.client.select(
                self.summaries_table,
                query={"select": "id", "id": f"eq.{summary_id}", "limit": "1"},
            )
            return bool(rows)
        except SupabaseRequestError:
            return False

    def _maybe_title_conversation(self, conversation_id: str, role: str, content: str) -> None:
        if role != "user":
            return
        rows = self.client.select(
            self.conversations_table,
            query={"select": "id,title", "id": f"eq.{conversation_id}", "limit": "1"},
        )
        if not rows:
            return
        title = rows[0].get("title", "")
        if title != "New Chat":
            return
        cleaned = " ".join(content.strip().split())[:60]
        if len(content.strip()) > 60:
            cleaned += "..."
        if cleaned:
            self.client.update(
                self.conversations_table,
                {"title": cleaned},
                query={"id": f"eq.{conversation_id}"},
                returning="minimal",
            )

    @staticmethod
    def _conversation_from_row(row: dict[str, Any]) -> GioConversation:
        return GioConversation(
            id=str(row["id"]),
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _message_from_row(row: dict[str, Any]) -> GioMessage:
        return GioMessage(
            id=str(row["id"]),
            conversation_id=str(row["conversation_id"]),
            role=row["role"],
            content=row["content"],
            provider=row.get("provider"),
            model=row.get("model"),
            thinking_content=row.get("thinking_content"),
            embedding=GioSupabaseRepository._normalize_embedding(row.get("embedding")),
            created_at=row["created_at"],
        )

    @staticmethod
    def _summary_from_row(row: dict[str, Any]) -> GioSummary:
        return GioSummary(
            id=str(row["id"]),
            conversation_id=str(row["conversation_id"]),
            content=row["content"],
            model=row.get("model"),
            embedding=GioSupabaseRepository._normalize_embedding(row.get("embedding")),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _dream_from_row(row: dict[str, Any]) -> GioDream:
        return GioDream(
            id=str(row["id"]),
            conversation_id=str(row["conversation_id"]),
            title=row["title"],
            content=row["content"],
            model=row.get("model"),
            source_message_ids=GioSupabaseRepository._normalize_string_list(row.get("source_message_ids")),
            embedding=GioSupabaseRepository._normalize_embedding(row.get("embedding")),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _normalize_embedding(value: Any) -> list[float] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [float(item) for item in parsed]
            except Exception:
                return None
        return None

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except Exception:
                return []
        return []

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

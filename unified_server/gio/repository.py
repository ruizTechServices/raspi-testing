from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from unified_server.core.conversations import derive_auto_title
from unified_server.settings import get_settings
from unified_server.gio.supabase_client import SupabaseRequestError, SupabaseRestClient


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


@dataclass(slots=True)
class GioKnowledgeDocument:
    id: str
    source_key: str
    title: str
    url: str | None
    tags: list[str]
    metadata: dict[str, Any]
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
        self.knowledge_documents_table = settings.GIO_KNOWLEDGE_DOCUMENTS_TABLE
        self.knowledge_chunks_table = settings.GIO_KNOWLEDGE_CHUNKS_TABLE
        self._summary_table_available: bool | None = None
        self._dream_table_available: bool | None = None
        self._knowledge_tables_available: bool | None = None

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
            self._knowledge_tables_available = self._detect_knowledge_tables()
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

    def get_messages(self, conversation_id: str, include_embeddings: bool = True) -> list[GioMessage]:
        # Embeddings are 1536 floats per message; skip the column entirely for
        # callers that never read them (UI listing, summary maintenance).
        columns = "id,conversation_id,role,content,provider,model,thinking_content,created_at"
        if include_embeddings:
            columns = "id,conversation_id,role,content,provider,model,thinking_content,embedding,created_at"
        rows = self.client.select(
            self.messages_table,
            query={
                "select": columns,
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

    def upsert_knowledge_document(
        self,
        *,
        source_key: str,
        title: str,
        url: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._knowledge_storage_available():
            raise RuntimeError(
                "Knowledge storage is missing. Apply the Supabase schema for gio_knowledge_documents and gio_knowledge_chunks first."
            )
        existing = self.client.select(
            self.knowledge_documents_table,
            query={
                "select": "id,source_key,title,url,tags,metadata,created_at,updated_at",
                "source_key": f"eq.{source_key}",
                "limit": "1",
            },
        )
        now = self._utc_now()
        payload = {
            "source_key": source_key,
            "title": title,
            "url": url,
            "tags": tags or [],
            "metadata": metadata or {},
            "updated_at": now,
        }
        if existing:
            rows = self.client.update(
                self.knowledge_documents_table,
                payload,
                query={"id": f"eq.{existing[0]['id']}"},
            )
            return rows[0]
        rows = self.client.insert(
            self.knowledge_documents_table,
            {"id": str(uuid4()), "created_at": now, **payload},
        )
        return rows[0]

    def replace_knowledge_chunks(self, *, document_id: str, chunks: list[dict[str, Any]]) -> None:
        if not self._knowledge_storage_available():
            raise RuntimeError(
                "Knowledge storage is missing. Apply the Supabase schema for gio_knowledge_documents and gio_knowledge_chunks first."
            )
        self.client.delete(
            self.knowledge_chunks_table,
            query={"document_id": f"eq.{document_id}"},
            returning="minimal",
        )
        if not chunks:
            return
        now = self._utc_now()
        payload = [
            {
                "id": str(uuid4()),
                "document_id": document_id,
                "chunk_index": item["chunk_index"],
                "content": item["content"],
                "token_count": item.get("token_count", 0),
                "embedding": item.get("embedding"),
                "created_at": now,
                "updated_at": now,
            }
            for item in chunks
        ]
        self.client.insert(self.knowledge_chunks_table, payload, returning="minimal")

    def search_knowledge_chunks(
        self,
        query_embedding: list[float],
        *,
        top_k: int,
        min_score: float,
    ) -> list[dict[str, Any]]:
        if not query_embedding or not self._knowledge_storage_available():
            return []
        try:
            result = self.client.rpc(
                "match_gio_knowledge_chunks",
                {
                    "query_embedding_text": self._embedding_to_vector_literal(query_embedding),
                    "match_count": top_k,
                    "min_score": min_score,
                },
            )
            return result if isinstance(result, list) else []
        except SupabaseRequestError:
            return []

    def list_knowledge_documents(self, *, limit: int = 500) -> list[dict[str, Any]]:
        if not self._knowledge_storage_available():
            return []
        try:
            return self.client.select(
                self.knowledge_documents_table,
                query={
                    "select": "id,source_key,title,url,tags,metadata,created_at,updated_at",
                    "order": "updated_at.desc",
                    "limit": str(limit),
                },
            )
        except SupabaseRequestError:
            return []

    def get_knowledge_chunks_for_document(self, document_id: str, *, limit: int = 3) -> list[dict[str, Any]]:
        if not self._knowledge_storage_available():
            return []
        try:
            return self.client.select(
                self.knowledge_chunks_table,
                query={
                    "select": "id,document_id,chunk_index,content,token_count,created_at,updated_at",
                    "document_id": f"eq.{document_id}",
                    "order": "chunk_index.asc",
                    "limit": str(limit),
                },
            )
        except SupabaseRequestError:
            return []

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

    def _knowledge_storage_available(self) -> bool:
        if self._knowledge_tables_available is None:
            self._knowledge_tables_available = self._detect_knowledge_tables()
        return self._knowledge_tables_available

    def _detect_knowledge_tables(self) -> bool:
        try:
            self.client.select(
                self.knowledge_documents_table,
                query={"select": "id", "limit": "1"},
            )
            self.client.select(
                self.knowledge_chunks_table,
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
        cleaned = derive_auto_title(content)
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
    def _embedding_to_vector_literal(values: list[float]) -> str:
        return "[" + ",".join(f"{float(value):.12g}" for value in values) + "]"

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

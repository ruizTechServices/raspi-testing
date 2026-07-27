from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from unified_server.gio.repository import GioSupabaseRepository
from unified_server.gio.tooling import GioContextSource, extract_query_terms
from unified_server.settings import get_settings


@dataclass(slots=True)
class GioKnowledgeChunkInput:
    content: str
    chunk_index: int
    token_count: int
    embedding: list[float] | None


class GioKnowledgeService:
    def __init__(self, repository: GioSupabaseRepository) -> None:
        self.repository = repository

    def search(self, query: str, query_embedding: list[float] | None) -> list[GioContextSource]:
        cleaned_query = query.strip()
        if not cleaned_query or not query_embedding:
            return []
        settings = get_settings()
        base_top_k = settings.GIO_KNOWLEDGE_TOP_K
        matches = self.repository.search_knowledge_chunks(
            query_embedding,
            top_k=max(base_top_k * 4, base_top_k),
            min_score=settings.GIO_KNOWLEDGE_MIN_SCORE,
        )
        reranked = self._rerank_matches(cleaned_query, matches)
        supplemented = self._supplement_with_lexical_matches(cleaned_query, reranked)
        final_matches = supplemented[:base_top_k]
        sources: list[GioContextSource] = []
        for index, item in enumerate(final_matches, start=1):
            snippet = " ".join(str(item.get("content") or "").split())[:900].strip()
            if not snippet:
                continue
            title = str(item.get("title") or item.get("source_key") or item.get("document_id") or "Knowledge")
            source_key = str(item.get("source_key") or title)
            url = item.get("url") or None
            score = item.get("score")
            score_value = float(score) if score is not None else None
            sources.append(
                GioContextSource(
                    kind="rag",
                    label=f"[R{index}]",
                    title=title,
                    source=source_key,
                    url=str(url) if url else None,
                    snippet=snippet,
                    score=score_value,
                    metadata={
                        "document_id": item.get("document_id"),
                        "chunk_id": item.get("chunk_id"),
                        "tags": item.get("tags") or [],
                        "rerank_score": float(item.get("rerank_score", score_value or 0.0)),
                    },
                )
            )
        return sources

    def _rerank_matches(self, query: str, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        terms = extract_query_terms(query)
        reranked: list[dict[str, Any]] = []
        for item in matches:
            source_key = str(item.get("source_key") or "").lower()
            title = str(item.get("title") or "").lower()
            content = str(item.get("content") or "").lower()
            combined = " ".join(part for part in (source_key, title, content) if part)
            score = float(item.get("score") or 0.0)
            bonus = 0.0
            for term in terms:
                if term in source_key:
                    bonus += 0.35
                elif term in title:
                    bonus += 0.2
                elif term in content:
                    bonus += 0.08
            if "stream" in terms or "streaming" in terms:
                if "chat/stream" in combined or "chat_stream" in combined or "response.output_text.delta" in combined:
                    bonus += 0.5
            if "route" in terms or "routing" in terms or "tool" in terms:
                if "tooling.py" in source_key or "web_search.py" in source_key or "knowledge.py" in source_key or "chat.py" in source_key:
                    bonus += 0.25
            reranked.append({**item, "rerank_score": score + bonus})
        reranked.sort(key=lambda item: float(item.get("rerank_score") or 0.0), reverse=True)
        return reranked

    def _supplement_with_lexical_matches(self, query: str, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        terms = extract_query_terms(query)
        if not terms:
            return matches

        existing_sources = {str(item.get("source_key") or "") for item in matches}
        supplemented = list(matches)
        documents = self.repository.list_knowledge_documents(limit=500)
        for document in documents:
            source_key = str(document.get("source_key") or "")
            lowered_source = source_key.lower()
            lowered_title = str(document.get("title") or "").lower()
            bonus = 0.0
            for term in terms:
                if term in lowered_source:
                    bonus += 0.5
                elif term in lowered_title:
                    bonus += 0.25
            if ("tool" in terms or "routing" in terms or "route" in terms) and "tooling.py" in lowered_source:
                bonus += 1.0
            if ("stream" in terms or "streaming" in terms) and ("web/gio.py" in lowered_source or "gio/chat.py" in lowered_source):
                bonus += 1.0
            if bonus <= 0.0 or source_key in existing_sources:
                continue

            chunks = self.repository.get_knowledge_chunks_for_document(str(document.get("id") or ""), limit=1)
            snippet = str((chunks[0].get("content") if chunks else "") or "").strip()
            if not snippet:
                continue
            supplemented.append(
                {
                    "chunk_id": chunks[0].get("id") if chunks else None,
                    "document_id": document.get("id"),
                    "source_key": source_key,
                    "title": document.get("title") or source_key,
                    "url": document.get("url"),
                    "tags": document.get("tags") or [],
                    "content": snippet,
                    "score": 0.0,
                    "rerank_score": bonus,
                }
            )
            existing_sources.add(source_key)

        supplemented.sort(key=lambda item: float(item.get("rerank_score") or item.get("score") or 0.0), reverse=True)
        return supplemented

    def upsert_document_with_chunks(
        self,
        *,
        source_key: str,
        title: str,
        chunks: list[GioKnowledgeChunkInput],
        url: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not source_key.strip():
            raise ValueError("source_key is required")
        if not title.strip():
            raise ValueError("title is required")
        document = self.repository.upsert_knowledge_document(
            source_key=source_key,
            title=title,
            url=url,
            tags=tags or [],
            metadata=metadata or {},
        )
        self.repository.replace_knowledge_chunks(
            document_id=str(document["id"]),
            chunks=[
                {
                    "content": item.content,
                    "chunk_index": item.chunk_index,
                    "token_count": item.token_count,
                    "embedding": item.embedding,
                }
                for item in chunks
                if item.content.strip()
            ],
        )
        return document


def iter_text_files(paths: list[str]) -> list[Path]:
    supported = {
        ".md",
        ".txt",
        ".rst",
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".html",
        ".css",
        ".sql",
        ".sh",
    }
    results: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.is_file() and path.suffix.lower() in supported:
            results.append(path)
            continue
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and child.suffix.lower() in supported:
                    results.append(child)
    return sorted(dict.fromkeys(results))


def chunk_text(text: str, *, chunk_size: int = 1800, overlap: int = 250) -> list[str]:
    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        if end < len(cleaned):
            split = cleaned.rfind("\n\n", start, end)
            if split == -1:
                split = cleaned.rfind("\n", start, end)
            if split == -1:
                split = cleaned.rfind(" ", start, end)
            if split != -1 and split > start + max(200, chunk_size // 3):
                end = split
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks

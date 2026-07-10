from __future__ import annotations

from typing import Callable

from unified_server.gio.embeddings import cosine_similarity
from unified_server.gio.heuristics import message_is_correction_like, truncate_content
from unified_server.gio.repository import GioDream, GioMessage, GioSupabaseRepository
from unified_server.settings import get_settings


class DreamGenerator:
    """Dream Mode: reflection entries distilled from a conversation's messages.

    `dream_from_sources` is an injectable callable seam (defaults to the real
    implementation) so the facade can expose it for tests.
    """

    def __init__(
        self,
        repository: GioSupabaseRepository,
        get_client: Callable[[], object | None],
        *,
        embed: Callable[[str], list[float] | None],
        dream_from_sources: Callable[..., tuple[str, str]] | None = None,
    ) -> None:
        self.repository = repository
        self._get_client = get_client
        self._embed = embed
        self._dream_from_sources = dream_from_sources or self.dream_from_sources

    def create_dream(self, conversation_id: str) -> GioDream:
        transcript_messages = self.repository.get_messages(conversation_id)
        source_messages = [item for item in transcript_messages if item.role in {"user", "assistant"} and item.content.strip()]
        if len(source_messages) < 4:
            raise ValueError("Dream Mode needs a little more conversation first.")

        latest_summary = self.repository.get_latest_summary(conversation_id)
        selected_messages = self.select_dream_sources(source_messages)
        selected_ids = [item.id for item in selected_messages]
        existing_dreams = self.repository.list_dreams(conversation_id)
        if existing_dreams and existing_dreams[0].source_message_ids == selected_ids:
            raise ValueError("No new material since the latest dream entry.")

        title, content = self._dream_from_sources(
            conversation_id, selected_messages, latest_summary.content if latest_summary else None
        )
        return self.repository.create_dream(
            conversation_id=conversation_id,
            title=title,
            content=content,
            model=get_settings().GIO_DREAM_MODEL,
            source_message_ids=selected_ids,
            embedding=self._embed(content),
        )

    def select_dream_sources(self, messages: list[GioMessage]) -> list[GioMessage]:
        limit = get_settings().GIO_DREAM_SOURCE_LIMIT
        recent = messages[-min(4, len(messages)):]
        older = messages[:-len(recent)] if len(messages) > len(recent) else []

        selected: list[GioMessage] = []
        seen_ids: set[str] = set()
        for item in recent:
            selected.append(item)
            seen_ids.add(item.id)

        correction_candidates = [item for item in older if message_is_correction_like(item)]
        for item in correction_candidates[-2:]:
            if item.id in seen_ids:
                continue
            selected.append(item)
            seen_ids.add(item.id)
            if len(selected) >= limit:
                return sorted(selected, key=lambda entry: entry.created_at)

        scored: list[tuple[float, GioMessage]] = []
        for item in older:
            if item.id in seen_ids or not item.embedding:
                continue
            scored.append((self.dream_source_priority(item, older), item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        for _, item in scored:
            if item.id in seen_ids:
                continue
            selected.append(item)
            seen_ids.add(item.id)
            if len(selected) >= limit:
                break
        return sorted(selected, key=lambda item: item.created_at)

    def dream_from_sources(
        self,
        conversation_id: str,
        messages: list[GioMessage],
        latest_summary: str | None,
    ) -> tuple[str, str]:
        client = self._get_client()
        if not client:
            raise ValueError("Dream Mode requires OPENAI_API_KEY for now.")

        transcript_lines = [f"{item.role}: {truncate_content(item.content, limit=280)}" for item in messages]
        prompt = [
            "You are generating a Dream Mode reflection for a single conversation.",
            "This is not a user-facing reply and not roleplay.",
            "Work only from the supplied evidence.",
            "Extract repeated themes, durable facts, unresolved threads, corrections, and any candidate long-term memories.",
            "Be concrete. Avoid mysticism, filler, and fake feelings.",
            "Return plain text in exactly this shape:",
            "Title: <short title>",
            "",
            "Reflection:",
            "- bullet",
            "- bullet",
            "",
            "Possible lasting memory:",
            "- bullet",
            "- bullet",
            "",
            "Open questions:",
            "- bullet",
            "- bullet",
        ]
        if latest_summary:
            prompt.extend(["", "Latest rolling summary:", latest_summary])
        prompt.extend(["", f"Conversation id: {conversation_id}", "Selected source excerpts:"])
        prompt.extend(transcript_lines)

        response = client.responses.create(
            model=get_settings().GIO_DREAM_MODEL,
            input=[{"role": "system", "content": "\n".join(prompt)}],
            store=False,
        )
        raw = getattr(response, "output_text", "").strip()
        if not raw:
            raise ValueError("Dream generation returned no content.")

        title = "Dream Reflection"
        body = raw
        first_line, _, remainder = raw.partition("\n")
        if first_line.lower().startswith("title:"):
            parsed = first_line.split(":", 1)[1].strip()
            title = parsed or title
            body = remainder.strip() or raw
        return title, body

    def dream_source_priority(self, candidate: GioMessage, pool: list[GioMessage]) -> float:
        score = 0.0
        if message_is_correction_like(candidate):
            score += 0.75
        if candidate.role == 'user':
            score += 0.15
        similarity_total = 0.0
        similarity_count = 0
        if candidate.embedding:
            for other in pool:
                if other.id == candidate.id or not other.embedding:
                    continue
                similarity_total += cosine_similarity(candidate.embedding, other.embedding)
                similarity_count += 1
        if similarity_count:
            score += similarity_total / similarity_count
        return score

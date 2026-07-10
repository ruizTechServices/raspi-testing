from __future__ import annotations

from difflib import SequenceMatcher
from typing import Callable

from unified_server.gio.heuristics import messages_include_summary_worthy_update, truncate_content
from unified_server.gio.repository import GioMessage, GioSupabaseRepository
from unified_server.settings import get_settings


class SummaryMaintainer:
    """Keeps one rolling summary per conversation up to date.

    `summarize` and `embed` are injectable callables so the facade can expose
    them as patchable seams; they default to the real implementations.
    """

    def __init__(
        self,
        repository: GioSupabaseRepository,
        get_client: Callable[[], object | None],
        *,
        embed: Callable[[str], list[float] | None],
        summarize: Callable[..., str | None] | None = None,
    ) -> None:
        self.repository = repository
        self._get_client = get_client
        self._embed = embed
        self._summarize = summarize or self.summarize_messages

    def maybe_update_rolling_summary(self, conversation_id: str) -> None:
        settings = get_settings()
        all_messages = self.repository.get_messages(conversation_id)
        visible_messages = [item for item in all_messages if item.role in {"user", "assistant", "system"}]
        latest_summary = self.repository.get_latest_summary(conversation_id)
        recent_messages = visible_messages[-settings.GIO_RECENT_MESSAGES_LIMIT:]
        recent_ids = {item.id for item in recent_messages}
        force_refresh = messages_include_summary_worthy_update(recent_messages)

        if latest_summary:
            candidates = [
                item for item in visible_messages if item.created_at > latest_summary.updated_at and item.id not in recent_ids
            ]
        else:
            candidates = [item for item in visible_messages if item.id not in recent_ids]

        if force_refresh:
            candidate_map = {item.id: item for item in candidates}
            for item in recent_messages:
                candidate_map[item.id] = item
            candidates = sorted(candidate_map.values(), key=lambda item: item.created_at)

        if len(candidates) < settings.GIO_SUMMARY_TRIGGER_MESSAGES and not force_refresh:
            return

        summary_text = self._summarize(candidates, latest_summary.content if latest_summary else None)
        if not summary_text:
            return
        if latest_summary and self.summary_equivalent(summary_text, latest_summary.content):
            return

        summary_embedding = self._embed(summary_text)
        self.repository.save_summary(
            conversation_id=conversation_id,
            content=summary_text,
            model=settings.GIO_SUMMARY_MODEL,
            embedding=summary_embedding,
        )

    def summarize_messages(self, messages: list[GioMessage], previous_summary: str | None = None) -> str | None:
        client = self._get_client()
        if not client or not messages:
            return previous_summary

        transcript_lines = [f"{item.role}: {truncate_content(item.content, limit=400)}" for item in messages]
        prompt = [
            "Create a compact rolling summary of the conversation.",
            "Keep durable facts, preferences, goals, decisions, and unresolved tasks.",
            "Drop filler, repetition, and small talk.",
            "Return plain text bullets only.",
            "Avoid repeating bullets that are already captured unless they need correction.",
        ]
        if previous_summary:
            prompt.append("Previous rolling summary:")
            prompt.append(previous_summary)
        prompt.append("New conversation segment:")
        prompt.extend(transcript_lines)

        try:
            response = client.responses.create(
                model=get_settings().GIO_SUMMARY_MODEL,
                input=[{"role": "system", "content": "\n".join(prompt)}],
                store=False,
            )
            summary = getattr(response, "output_text", "").strip()
            return summary or previous_summary
        except Exception:
            return previous_summary

    @staticmethod
    def summary_equivalent(left: str, right: str) -> bool:
        normalized_left = "\n".join(line.strip() for line in left.splitlines() if line.strip())
        normalized_right = "\n".join(line.strip() for line in right.splitlines() if line.strip())
        if normalized_left == normalized_right:
            return True
        return SequenceMatcher(None, normalized_left, normalized_right).ratio() >= 0.98

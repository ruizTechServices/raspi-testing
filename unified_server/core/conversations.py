from __future__ import annotations

from typing import Protocol

AUTO_TITLE_MAX_LENGTH = 60


class ConversationStore(Protocol):
    """Shared surface of the SQLite and Supabase conversation repositories."""

    def conversation_exists(self, conversation_id: str) -> bool: ...

    def delete_conversation(self, conversation_id: str) -> None: ...


def require_conversation(
    store: ConversationStore,
    conversation_id: str,
    not_found_message: str = "Conversation not found.",
) -> str:
    """Validate that a conversation id is present and exists; returns the cleaned id."""
    cleaned = (conversation_id or "").strip()
    if not cleaned:
        raise ValueError("conversation_id is required.")
    if not store.conversation_exists(cleaned):
        raise ValueError(not_found_message)
    return cleaned


def derive_auto_title(content: str) -> str:
    """First-user-message auto-title: whitespace-collapsed, capped at 60 chars."""
    cleaned = content.strip()
    title = " ".join(cleaned.split())[:AUTO_TITLE_MAX_LENGTH]
    if len(cleaned) > AUTO_TITLE_MAX_LENGTH:
        title += "..."
    return title

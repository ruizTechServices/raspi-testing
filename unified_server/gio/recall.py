from __future__ import annotations

from unified_server.gio.embeddings import cosine_similarity
from unified_server.gio.heuristics import truncate_content
from unified_server.gio.repository import GioMessage
from unified_server.settings import get_settings


def build_recall_block(
    conversation_messages: list[GioMessage],
    recent_messages: list[GioMessage],
    user_embedding: list[float] | None,
) -> str | None:
    """Semantic recall over earlier messages in the same conversation.

    Scores every non-recent user/assistant message with an embedding against
    the current user message and returns a system-prompt block with the best
    snippets, or None when nothing clears the threshold.
    """
    if not user_embedding:
        return None

    settings = get_settings()
    recent_ids = {item.id for item in recent_messages}
    seen_snippets: set[str] = set()
    user_matches: list[str] = []
    assistant_matches: list[str] = []
    scored_candidates: list[tuple[float, GioMessage]] = []

    for item in conversation_messages:
        if item.id in recent_ids:
            continue
        if item.role not in {"user", "assistant"}:
            continue
        if not item.embedding:
            continue
        score = cosine_similarity(user_embedding, item.embedding)
        if score >= settings.GIO_RECALL_MIN_SCORE:
            scored_candidates.append((score, item))

    if not scored_candidates:
        return None

    scored_candidates.sort(key=lambda pair: pair[0], reverse=True)
    for _, item in scored_candidates:
        snippet = truncate_content(item.content)
        fingerprint = snippet.lower()
        if fingerprint in seen_snippets:
            continue
        seen_snippets.add(fingerprint)
        target = user_matches if item.role == "user" else assistant_matches
        target.append(snippet)
        if len(user_matches) + len(assistant_matches) >= settings.GIO_RECALL_TOP_K:
            break

    if not user_matches and not assistant_matches:
        return None

    lines = [
        "Relevant earlier context from this same conversation.",
        "Use it only when it genuinely helps answer the current message.",
    ]
    if user_matches:
        lines.append("User-side recalled context:")
        lines.extend(f"- {snippet}" for snippet in user_matches)
    if assistant_matches:
        lines.append("Assistant-side recalled context:")
        lines.extend(f"- {snippet}" for snippet in assistant_matches)
    return "\n".join(lines)

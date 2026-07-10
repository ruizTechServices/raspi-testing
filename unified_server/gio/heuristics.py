from __future__ import annotations

from unified_server.gio.repository import GioMessage


def truncate_content(content: str, limit: int = 240) -> str:
    cleaned = " ".join(content.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


UPDATE_MARKERS = [
    'correction:',
    'actually',
    'instead of',
    'not ',
    'now ',
    'changed to',
    'update:',
]


def messages_include_summary_worthy_update(messages: list[GioMessage]) -> bool:
    if not messages:
        return False
    for item in messages:
        if item.role != 'user':
            continue
        lowered = item.content.lower()
        if any(marker in lowered for marker in UPDATE_MARKERS):
            return True
    return False


def message_is_correction_like(message: GioMessage) -> bool:
    return message.role == 'user' and messages_include_summary_worthy_update([message])

from __future__ import annotations

from typing import Protocol


class ChatProvider(Protocol):
    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str: ...

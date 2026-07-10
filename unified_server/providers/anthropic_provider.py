from __future__ import annotations

import anthropic

from unified_server.settings import get_settings

ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-20250514"


class AnthropicProvider:
    """Anthropic chat. The SDK client is built lazily on first use so a key
    added after startup is picked up without a restart."""

    def __init__(self) -> None:
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic | None:
        if self._client is None:
            api_key = get_settings().ANTHROPIC_API_KEY
            if api_key:
                self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        if not self.client:
            raise ValueError("ANTHROPIC_API_KEY is not set.")

        system_parts = []
        non_system_messages = []
        for message in messages:
            if message["role"] == "system":
                system_parts.append(message["content"])
            else:
                non_system_messages.append(message)

        response = self.client.messages.create(
            model=model or ANTHROPIC_DEFAULT_MODEL,
            max_tokens=2048,
            system="\n".join(system_parts).strip() or None,
            messages=non_system_messages,
        )

        chunks = []
        for block in response.content:
            if getattr(block, "type", "") == "text":
                chunks.append(block.text)
        return "".join(chunks).strip()

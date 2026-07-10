from __future__ import annotations

from openai import OpenAI

from unified_server.settings import get_settings


class OpenAIProvider:
    """OpenAI chat via the Responses API. The SDK client is built lazily on
    first use so a key added after startup is picked up without a restart."""

    def __init__(self) -> None:
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI | None:
        if self._client is None:
            api_key = get_settings().OPENAI_API_KEY
            if api_key:
                self._client = OpenAI(api_key=api_key)
        return self._client

    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        if not self.client:
            raise ValueError("OPENAI_API_KEY is not set.")
        response = self.client.responses.create(
            model=model or get_settings().DEFAULT_MODEL,
            input=messages,
            store=False,
        )
        return getattr(response, "output_text", "").strip()

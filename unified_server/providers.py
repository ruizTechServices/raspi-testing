from __future__ import annotations

from typing import Protocol

import anthropic
import requests
from openai import OpenAI

from unified_server.config import (
    ANTHROPIC_API_KEY,
    DEFAULT_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
)


class ChatProvider(Protocol):
    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str: ...


class OpenAIProvider:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        if not self.client:
            raise ValueError("OPENAI_API_KEY is not set.")
        response = self.client.responses.create(
            model=model or DEFAULT_MODEL,
            input=messages,
            store=False,
        )
        return getattr(response, "output_text", "").strip()


class OllamaProvider:
    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": model or OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "").strip()


class AnthropicProvider:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

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
            model=model or "claude-sonnet-4-20250514",
            max_tokens=2048,
            system="\n".join(system_parts).strip() or None,
            messages=non_system_messages,
        )

        chunks = []
        for block in response.content:
            if getattr(block, "type", "") == "text":
                chunks.append(block.text)
        return "".join(chunks).strip()


class ProviderRegistry:
    def __init__(self) -> None:
        self.providers = {
            "openai": OpenAIProvider(),
            "ollama": OllamaProvider(),
            "anthropic": AnthropicProvider(),
        }

    def get(self, name: str) -> ChatProvider:
        if name not in self.providers:
            raise ValueError(f"Unsupported provider: {name}")
        return self.providers[name]

    def list_providers(self) -> list[dict[str, object]]:
        return [
            {"id": "openai", "configured": bool(OPENAI_API_KEY)},
            {"id": "ollama", "configured": True},
            {"id": "anthropic", "configured": bool(ANTHROPIC_API_KEY)},
        ]

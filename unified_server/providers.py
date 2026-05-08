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

OPENAI_MODELS = [
    "gpt-4.1-mini",
    "gpt-4o-mini",
    "gpt-4o",
]

ANTHROPIC_MODELS = [
    "claude-3-5-haiku-latest",
    "claude-3-5-sonnet-latest",
    "claude-sonnet-4-20250514",
]


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
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={"model": model or OLLAMA_MODEL, "messages": messages, "stream": False},
                timeout=120,
            )
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "").strip()
        except requests.exceptions.ConnectionError as exc:
            raise ValueError("Ollama is offline. Turn on the Ollama server to continue.") from exc
        except requests.exceptions.Timeout as exc:
            raise ValueError("Ollama timed out while generating a reply. Check that the server is on and the model is responsive.") from exc
        except requests.exceptions.RequestException as exc:
            raise ValueError(f"Ollama request failed: {exc}") from exc


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
            {
                "id": "openai",
                "configured": bool(OPENAI_API_KEY),
                "models": OPENAI_MODELS,
                "default_model": "gpt-4.1-mini",
            },
            {
                "id": "ollama",
                "configured": True,
                "models": self._list_ollama_models(),
                "default_model": OLLAMA_MODEL,
            },
            {
                "id": "anthropic",
                "configured": bool(ANTHROPIC_API_KEY),
                "models": ANTHROPIC_MODELS,
                "default_model": "claude-sonnet-4-20250514",
            },
        ]

    def _list_ollama_models(self) -> list[str]:
        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
            response.raise_for_status()
            models = response.json().get("models", [])
            names = [item.get("name", "").strip() for item in models if item.get("name")]
            return names or [OLLAMA_MODEL]
        except Exception:
            return [OLLAMA_MODEL]

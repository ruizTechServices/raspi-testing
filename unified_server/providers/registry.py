from __future__ import annotations

import requests

from unified_server.providers.anthropic_provider import ANTHROPIC_DEFAULT_MODEL, AnthropicProvider
from unified_server.providers.base import ChatProvider
from unified_server.providers.ollama_provider import OllamaProvider
from unified_server.providers.openai_provider import OpenAIProvider
from unified_server.settings import get_settings

OPENAI_MODELS = [
    "gpt-4.1-mini",
    "gpt-4o-mini",
    "gpt-4o",
]

ANTHROPIC_MODELS = [
    "claude-3-5-haiku-latest",
    "claude-3-5-sonnet-latest",
    ANTHROPIC_DEFAULT_MODEL,
]

OPENAI_DEFAULT_MODEL = "gpt-4.1-mini"


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
        settings = get_settings()
        return [
            {
                "id": "openai",
                "configured": bool(settings.OPENAI_API_KEY),
                "models": OPENAI_MODELS,
                "default_model": OPENAI_DEFAULT_MODEL,
            },
            {
                "id": "ollama",
                "configured": True,
                "models": self._list_ollama_models(),
                "default_model": settings.OLLAMA_MODEL,
            },
            {
                "id": "anthropic",
                "configured": bool(settings.ANTHROPIC_API_KEY),
                "models": ANTHROPIC_MODELS,
                "default_model": ANTHROPIC_DEFAULT_MODEL,
            },
        ]

    def _list_ollama_models(self) -> list[str]:
        settings = get_settings()
        try:
            response = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=10)
            response.raise_for_status()
            models = response.json().get("models", [])
            names = [item.get("name", "").strip() for item in models if item.get("name")]
            return names or [settings.OLLAMA_MODEL]
        except requests.exceptions.RequestException:
            return [settings.OLLAMA_MODEL]

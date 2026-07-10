from __future__ import annotations

from typing import Any, Callable

from unified_server.providers import OPENAI_MODELS
from unified_server.settings import get_settings

BLOCKED_MODEL_TOKENS = [
    'instruct',
    'audio',
    'realtime',
    'search',
    'transcribe',
    'tts',
    'image',
    'codex',
    'chat-latest',
    'pro',
]

ALLOWED_MODEL_PREFIXES = ['gpt-4.1', 'gpt-4o']


def is_supported_gio_model(model_id: str) -> bool:
    lowered = (model_id or '').lower().strip()
    if not lowered.startswith('gpt'):
        return False
    if any(token in lowered for token in BLOCKED_MODEL_TOKENS):
        return False
    return any(lowered.startswith(prefix) for prefix in ALLOWED_MODEL_PREFIXES)


def supports_reasoning(model_id: str) -> bool:
    lowered = model_id.lower()
    return any(token in lowered for token in ["o1", "o3", "o4", "reasoning"])


class ModelCatalog:
    def __init__(self, get_client: Callable[[], object | None]) -> None:
        self._get_client = get_client

    def list_models(self) -> dict[str, Any]:
        models = self.list_openai_models()
        default = get_settings().GIO_DEFAULT_MODEL
        default_model = default if any(item["id"] == default for item in models) else (models[0]["id"] if models else default)
        return {
            "provider": "openai",
            "default_model": default_model,
            "models": models,
        }

    def list_openai_models(self) -> list[dict[str, Any]]:
        client = self._get_client()
        if not client:
            return [{"id": model, "supports_reasoning": False} for model in OPENAI_MODELS]
        try:
            response = client.models.list()
            items = []
            for model in response.data:
                model_id = getattr(model, "id", "")
                if not is_supported_gio_model(model_id):
                    continue
                items.append(
                    {
                        "id": model_id,
                        "supports_reasoning": supports_reasoning(model_id),
                    }
                )
            unique = {item["id"]: item for item in items}
            return sorted(unique.values(), key=lambda item: item["id"])
        except Exception:
            return [{"id": model, "supports_reasoning": supports_reasoning(model)} for model in OPENAI_MODELS]

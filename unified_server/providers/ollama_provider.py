from __future__ import annotations

import requests

from unified_server.settings import get_settings


class OllamaProvider:
    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        settings = get_settings()
        try:
            response = requests.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={"model": model or settings.OLLAMA_MODEL, "messages": messages, "stream": False},
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

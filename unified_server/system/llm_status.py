from __future__ import annotations

import time

import requests

from unified_server.settings import get_settings


def _probe_ollama_status() -> dict[str, object]:
    ollama_base_url = get_settings().OLLAMA_BASE_URL
    try:
        response = requests.get(f"{ollama_base_url}/api/tags", timeout=8)
        response.raise_for_status()
        models = response.json().get("models", [])
        return {
            "provider": "ollama",
            "ok": True,
            "status": "online",
            "detail": f"Reachable at {ollama_base_url}.",
            "models": [item.get("name", "").strip() for item in models if item.get("name")],
        }
    except requests.exceptions.ConnectionError as exc:
        return {
            "provider": "ollama",
            "ok": False,
            "status": "offline",
            "detail": f"Ollama is not reachable at {ollama_base_url}.",
            "error": str(exc),
            "models": [],
        }
    except requests.exceptions.Timeout as exc:
        return {
            "provider": "ollama",
            "ok": False,
            "status": "timeout",
            "detail": "Ollama timed out while responding.",
            "error": str(exc),
            "models": [],
        }
    except requests.exceptions.RequestException as exc:
        return {
            "provider": "ollama",
            "ok": False,
            "status": "error",
            "detail": "Ollama returned an unexpected error.",
            "error": str(exc),
            "models": [],
        }


def _probe_openai_status() -> dict[str, object]:
    openai_api_key = get_settings().OPENAI_API_KEY
    if not openai_api_key:
        return {
            "provider": "openai",
            "ok": False,
            "status": "not_configured",
            "detail": "OPENAI_API_KEY is not configured.",
        }

    try:
        response = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {openai_api_key}"},
            timeout=10,
        )
        if response.status_code == 200:
            return {
                "provider": "openai",
                "ok": True,
                "status": "online",
                "detail": "OpenAI API is reachable.",
            }
        if response.status_code == 401:
            return {
                "provider": "openai",
                "ok": False,
                "status": "unauthorized",
                "detail": "OpenAI rejected the API key.",
                "error": response.text,
            }
        if response.status_code == 429:
            return {
                "provider": "openai",
                "ok": False,
                "status": "quota",
                "detail": "OpenAI is reachable, but the account is out of quota or rate-limited.",
                "error": response.text,
            }
        return {
            "provider": "openai",
            "ok": False,
            "status": "error",
            "detail": f"OpenAI returned HTTP {response.status_code}.",
            "error": response.text,
        }
    except requests.exceptions.Timeout as exc:
        return {
            "provider": "openai",
            "ok": False,
            "status": "timeout",
            "detail": "OpenAI timed out while responding.",
            "error": str(exc),
        }
    except requests.exceptions.RequestException as exc:
        return {
            "provider": "openai",
            "ok": False,
            "status": "error",
            "detail": "OpenAI is not reachable from this server.",
            "error": str(exc),
        }


def get_llm_status_snapshot() -> dict[str, object]:
    checks = [_probe_ollama_status(), _probe_openai_status()]
    return {
        "status": "ok",
        "checks": checks,
        "checked_at": time.time(),
    }

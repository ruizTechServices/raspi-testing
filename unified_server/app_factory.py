from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import time

from flask import Flask, Response, jsonify, request, send_file, stream_with_context
import requests
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from unified_server.database import init_db
from unified_server.gio_service import GioService
from unified_server.razzy_service import RazzyService
from unified_server.security import attach_security_headers, require_api_key
from unified_server.service import ChatService
from unified_server.settings import get_settings
from unified_server.twitter_service import TwitterClientConfigError, TwitterClientError, TwitterService


PI_TEMPERATURE_CACHE_TTL_SECONDS = 15
_pi_temperature_cache: dict[str, float | str | None] = {
    "temperature_c": None,
    "temperature_f": None,
    "fetched_at": None,
}


def _read_pi_temperature_c() -> float:
    raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text(encoding="utf-8").strip()
    return int(raw) / 1000.0


def _temperature_state(temperature_c: float) -> tuple[str, str]:
    if temperature_c < 55:
        return "cool", "Cool, plenty of thermal headroom."
    if temperature_c < 70:
        return "normal", "Normal operating range for the Pi."
    if temperature_c < 80:
        return "warm", "Warm, but still acceptable under load."
    return "hot", "Hot. Ease sustained load or improve cooling if this persists."


def _build_temperature_payload(
    temperature_c: float,
    fetched_at: float,
    *,
    cached: bool,
    age_seconds: float,
) -> dict[str, object]:
    temperature_f = round((temperature_c * 9 / 5) + 32, 1)
    state, advisory = _temperature_state(temperature_c)
    return {
        "temperature_c": temperature_c,
        "temperature_f": temperature_f,
        "thermal_state": state,
        "advisory": advisory,
        "cached": cached,
        "cache_ttl_seconds": PI_TEMPERATURE_CACHE_TTL_SECONDS,
        "age_seconds": round(age_seconds, 1),
        "fetched_at": fetched_at,
    }


def _get_pi_temperature_snapshot(now: float | None = None) -> dict[str, object]:
    current_time = now if now is not None else time.time()
    fetched_at = _pi_temperature_cache.get("fetched_at")
    if isinstance(fetched_at, (int, float)) and _pi_temperature_cache.get("temperature_c") is not None:
        age_seconds = current_time - fetched_at
        if age_seconds < PI_TEMPERATURE_CACHE_TTL_SECONDS:
            return _build_temperature_payload(
                float(_pi_temperature_cache["temperature_c"]),
                fetched_at,
                cached=True,
                age_seconds=age_seconds,
            )

    temperature_c = round(_read_pi_temperature_c(), 1)
    _pi_temperature_cache["temperature_c"] = temperature_c
    _pi_temperature_cache["temperature_f"] = round((temperature_c * 9 / 5) + 32, 1)
    _pi_temperature_cache["fetched_at"] = current_time
    return _build_temperature_payload(
        temperature_c,
        current_time,
        cached=False,
        age_seconds=0.0,
    )


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


def _get_llm_status_snapshot() -> dict[str, object]:
    checks = [_probe_ollama_status(), _probe_openai_status()]
    return {
        "status": "ok",
        "checks": checks,
        "checked_at": time.time(),
    }


def _systemctl_ollama(action: str) -> dict[str, object]:
    allowed_actions = {"start", "stop", "restart", "status"}
    if action not in allowed_actions:
        raise ValueError("Unsupported ollama action.")

    systemctl_prefix = ["sudo", "/bin/systemctl"]

    if action == "status":
        command = [*systemctl_prefix, "is-active", "ollama.service"]
    else:
        command = [*systemctl_prefix, action, "ollama.service"]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=25)
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "action": action,
            "detail": f"Ollama {action} timed out.",
            "stdout": (exc.stdout or "").strip(),
            "stderr": (exc.stderr or "").strip(),
        }

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if action == "status":
        active = stdout == "active"
        return {
            "ok": result.returncode == 0,
            "action": action,
            "service_state": stdout or "unknown",
            "detail": "Ollama service is active." if active else f"Ollama service state: {stdout or 'unknown' }.",
            "stdout": stdout,
            "stderr": stderr,
        }

    state_check = _systemctl_ollama("status")
    detail = f"Ollama {action} command completed." if result.returncode == 0 else f"Ollama {action} command failed."
    return {
        "ok": result.returncode == 0,
        "action": action,
        "detail": detail,
        "service_state": state_check.get("service_state", "unknown"),
        "stdout": stdout,
        "stderr": stderr,
    }


def create_app(
    service: ChatService | None = None,
    razzy_service: RazzyService | None = None,
    twitter_service: TwitterService | None = None,
    gio_service: GioService | None = None,
) -> Flask:
    settings = get_settings()
    init_db()
    app = Flask(__name__)
    app.config["ENV"] = settings.FLASK_ENV

    CORS(app, origins=settings.ALLOWED_ORIGINS)
    Limiter(get_remote_address, app=app, default_limits=["120 per minute"], storage_uri="memory://")
    attach_security_headers(app)
    service = service or ChatService()
    razzy_service = razzy_service or RazzyService()
    twitter_service = twitter_service or TwitterService()
    gio_service = gio_service or GioService()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/system/temperature")
    def system_temperature():
        try:
            return jsonify({"status": "ok", **_get_pi_temperature_snapshot()})
        except Exception as exc:
            return jsonify({"error": f"Unable to read Pi temperature: {exc}"}), 502

    @app.get("/api/system/llm-status")
    def system_llm_status():
        try:
            return jsonify(_get_llm_status_snapshot())
        except Exception as exc:
            return jsonify({"error": f"Unable to check LLM status: {exc}"}), 502

    @app.post("/api/system/ollama/control")
    @require_api_key
    def system_ollama_control():
        payload = request.get_json(silent=True) or {}
        action = str(payload.get("action", "")).strip().lower()
        if action not in {"start", "stop", "restart", "status"}:
            return jsonify({"error": "Invalid Ollama action. Use start, stop, restart, or status."}), 400
        try:
            result = _systemctl_ollama(action)
            status_code = 200 if result.get("ok") else 502
            return jsonify({"status": "ok" if result.get("ok") else "error", **result}), status_code
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": f"Unable to control Ollama service: {exc}"}), 502

    @app.get("/api/providers")
    def list_providers():
        return jsonify({"providers": service.providers.list_providers()})

    @app.post("/api/conversations")
    @require_api_key
    def create_conversation():
        data = request.get_json(silent=True) or {}
        title = data.get("title", "New Chat")
        conversation_id = service.create_conversation(title=title)
        return jsonify({"conversation_id": conversation_id, "title": title})

    @app.get("/api/conversations")
    @require_api_key
    def list_conversations():
        items = [asdict(item) for item in service.list_conversations()]
        return jsonify({"conversations": items})

    @app.get("/api/conversations/<conversation_id>/messages")
    @require_api_key
    def get_messages(conversation_id: str):
        try:
            items = [asdict(item) for item in service.get_messages(conversation_id)]
            return jsonify({"conversation_id": conversation_id, "messages": items})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.patch("/api/conversations/<conversation_id>")
    @require_api_key
    def rename_conversation(conversation_id: str):
        data = request.get_json(silent=True) or {}
        title = data.get("title", "")
        try:
            return jsonify(service.rename_conversation(conversation_id, title))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.delete("/api/conversations/<conversation_id>")
    @require_api_key
    def delete_conversation(conversation_id: str):
        try:
            service.delete_conversation(conversation_id)
            return jsonify({"ok": True, "conversation_id": conversation_id})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/chat")
    @require_api_key
    def chat():
        data = request.get_json(silent=True) or {}
        conversation_id = data.get("conversation_id")
        user_text = data.get("message", "")
        provider = data.get("provider")
        model = data.get("model")

        if not conversation_id:
            conversation_id = service.create_conversation(title="New Chat")

        try:
            result = service.chat(
                conversation_id=conversation_id,
                user_text=user_text,
                provider_name=provider,
                model=model,
            )
            return jsonify(result)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502
    
    @app.get("/")
    def index_ui():
        html_path = Path(__file__).resolve().parent / "static" / "index.html"
        return send_file(html_path)

    @app.get("/console")
    def console_ui():
        html_path = Path(__file__).resolve().parent / "static" / "console.html"
        return send_file(html_path)

    @app.get("/razzy")
    def razzy_ui():
        html_path = Path(__file__).resolve().parent / "static" / "razzy.html"
        return send_file(html_path)

    @app.get("/gio")
    def gio_ui():
        html_path = Path(__file__).resolve().parent / "static" / "gio.html"
        return send_file(html_path)

    @app.get("/gio/dreams")
    def gio_dreams_ui():
        html_path = Path(__file__).resolve().parent / "static" / "gio-dreams.html"
        return send_file(html_path)

    @app.get("/api/razzy/profile")
    def razzy_profile():
        return jsonify({"profile": razzy_service.profile()})

    @app.get("/api/twitter/status")
    @require_api_key
    def twitter_status():
        return jsonify({"twitter": twitter_service.status()})

    @app.get("/api/twitter/me")
    @require_api_key
    def twitter_me():
        try:
            return jsonify(twitter_service.get_me())
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientConfigError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientError as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/twitter/posts/<post_id>")
    @require_api_key
    def twitter_get_post(post_id: str):
        try:
            return jsonify(twitter_service.get_post(post_id))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientConfigError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientError as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/twitter/timeline/user/<user_id>")
    @require_api_key
    def twitter_user_timeline(user_id: str):
        max_results = request.args.get("max_results", default=10, type=int)
        try:
            return jsonify(twitter_service.get_user_timeline(user_id=user_id, max_results=max_results))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientConfigError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientError as exc:
            return jsonify({"error": str(exc)}), 502

    @app.post("/api/twitter/post")
    @require_api_key
    def twitter_create_post():
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        try:
            return jsonify(twitter_service.create_post(text)), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientConfigError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientError as exc:
            return jsonify({"error": str(exc)}), 502

    @app.post("/api/twitter/posts/<post_id>/reply")
    @require_api_key
    def twitter_reply(post_id: str):
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        try:
            return jsonify(twitter_service.reply_to_post(post_id, text)), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientConfigError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientError as exc:
            return jsonify({"error": str(exc)}), 502

    @app.post("/api/twitter/posts/<post_id>/quote")
    @require_api_key
    def twitter_quote(post_id: str):
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        try:
            return jsonify(twitter_service.quote_post(post_id, text)), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientConfigError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientError as exc:
            return jsonify({"error": str(exc)}), 502

    @app.delete("/api/twitter/posts/<post_id>")
    @require_api_key
    def twitter_delete_post(post_id: str):
        try:
            return jsonify(twitter_service.delete_post(post_id))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientConfigError as exc:
            return jsonify({"error": str(exc)}), 400
        except TwitterClientError as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/gio/models")
    @require_api_key
    def gio_models():
        try:
            return jsonify(gio_service.list_models())
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/gio/session")
    @require_api_key
    def gio_session():
        data = request.get_json(silent=True) or {}
        title = data.get("title", "New Chat")
        try:
            gio_service.ensure_schema()
            conversation = gio_service.create_conversation(title=title)
            return jsonify(conversation)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/gio/conversations")
    @require_api_key
    def gio_conversations():
        try:
            gio_service.ensure_schema()
            return jsonify({"conversations": gio_service.list_conversations()})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/gio/conversations/<conversation_id>/messages")
    @require_api_key
    def gio_messages(conversation_id: str):
        try:
            gio_service.ensure_schema()
            return jsonify({"conversation_id": conversation_id, "messages": gio_service.get_messages(conversation_id)})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.patch("/api/gio/conversations/<conversation_id>")
    @require_api_key
    def gio_rename_conversation(conversation_id: str):
        data = request.get_json(silent=True) or {}
        title = data.get("title", "")
        try:
            gio_service.ensure_schema()
            return jsonify(gio_service.rename_conversation(conversation_id, title))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.delete("/api/gio/conversations/<conversation_id>")
    @require_api_key
    def gio_delete_conversation(conversation_id: str):
        try:
            gio_service.ensure_schema()
            gio_service.delete_conversation(conversation_id)
            return jsonify({"ok": True, "conversation_id": conversation_id})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/gio/dreams")
    @require_api_key
    def gio_list_dreams():
        conversation_id = request.args.get("conversation_id")
        try:
            gio_service.ensure_schema()
            return jsonify({"dreams": gio_service.list_dreams(conversation_id=conversation_id)})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/gio/dreams/<dream_id>")
    @require_api_key
    def gio_get_dream(dream_id: str):
        try:
            gio_service.ensure_schema()
            return jsonify(gio_service.get_dream(dream_id))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.post("/api/gio/conversations/<conversation_id>/dream")
    @require_api_key
    def gio_create_dream(conversation_id: str):
        try:
            gio_service.ensure_schema()
            return jsonify(gio_service.create_dream(conversation_id)), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.post("/api/gio/chat")
    @require_api_key
    def gio_chat():
        data = request.get_json(silent=True) or {}
        conversation_id = data.get("conversation_id")
        message = data.get("message", "")
        provider = "openai"
        model = data.get("model")
        try:
            gio_service.ensure_schema()
            if not conversation_id:
                conversation_id = gio_service.create_conversation()["id"]
            return jsonify(gio_service.chat_once(conversation_id, message, provider, model))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.post("/api/gio/chat/stream")
    @require_api_key
    def gio_chat_stream():
        data = request.get_json(silent=True) or {}
        conversation_id = data.get("conversation_id")
        message = data.get("message", "")
        provider = "openai"
        model = data.get("model")

        def generate():
            try:
                gio_service.ensure_schema()
                cid = conversation_id or gio_service.create_conversation()["id"]
                for event in gio_service.chat_stream(cid, message, provider, model):
                    yield json.dumps(event, separators=(",", ":")) + "\n"
            except ValueError as exc:
                yield json.dumps({"type": "error", "error": str(exc)}, separators=(",", ":")) + "\n"
            except Exception as exc:
                yield json.dumps({"type": "error", "error": str(exc)}, separators=(",", ":")) + "\n"

        return Response(stream_with_context(generate()), mimetype="application/x-ndjson")

    @app.post("/api/razzy/session")
    @require_api_key
    def razzy_session():
        return jsonify({"error": "Razzy chat has been removed from this page."}), 410

    @app.post("/api/razzy/chat")
    @require_api_key
    def razzy_chat():
        return jsonify({"error": "Razzy chat has been removed from this page."}), 410

    @app.post("/api/razzy/remember")
    @require_api_key
    def razzy_remember():
        return jsonify({"error": "Razzy chat memory has been removed from this page."}), 410

    @app.get("/api/razzy/memory/<conversation_id>")
    @require_api_key
    def razzy_memory(conversation_id: str):
        return jsonify({"error": "Razzy chat memory has been removed from this page."}), 410

    return app

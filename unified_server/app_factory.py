from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from unified_server.config import ALLOWED_ORIGINS, FLASK_ENV
from unified_server.database import init_db
from unified_server.razzy_service import RazzyService
from unified_server.security import attach_security_headers, require_api_key
from unified_server.service import ChatService


def create_app(service: ChatService | None = None, razzy_service: RazzyService | None = None) -> Flask:
    init_db()
    app = Flask(__name__)
    app.config["ENV"] = FLASK_ENV

    CORS(app, origins=ALLOWED_ORIGINS)
    Limiter(get_remote_address, app=app, default_limits=["120 per minute"], storage_uri="memory://")
    attach_security_headers(app)
    service = service or ChatService()
    razzy_service = razzy_service or RazzyService()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

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
        items = [asdict(item) for item in service.get_messages(conversation_id)]
        return jsonify({"conversation_id": conversation_id, "messages": items})

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

    @app.get("/razzy")
    def razzy_ui():
        html_path = Path(__file__).resolve().parent / "static" / "razzy.html"
        return send_file(html_path)

    @app.get("/api/razzy/profile")
    def razzy_profile():
        return jsonify({"profile": razzy_service.profile()})

    @app.post("/api/razzy/session")
    @require_api_key
    def razzy_session():
        data = request.get_json(silent=True) or {}
        title = data.get("title", "Razzy Chat")
        conversation_id = razzy_service.create_session(title=title)
        return jsonify({"conversation_id": conversation_id, "title": title})

    @app.post("/api/razzy/chat")
    @require_api_key
    def razzy_chat():
        data = request.get_json(silent=True) or {}
        conversation_id = data.get("conversation_id") or razzy_service.create_session()
        message = data.get("message", "")
        provider = data.get("provider")
        model = data.get("model")
        try:
            return jsonify(razzy_service.chat(conversation_id, message, provider, model))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.post("/api/razzy/remember")
    @require_api_key
    def razzy_remember():
        data = request.get_json(silent=True) or {}
        conversation_id = data.get("conversation_id")
        content = data.get("content", "")
        cell_type = data.get("cell_type", "fact")
        salience = float(data.get("salience", 0.8))
        if not conversation_id:
            return jsonify({"error": "conversation_id is required."}), 400
        try:
            memory_id = razzy_service.remember(conversation_id, content, cell_type, salience)
            return jsonify({"ok": True, "memory_id": memory_id})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/razzy/memory/<conversation_id>")
    @require_api_key
    def razzy_memory(conversation_id: str):
        return jsonify({"conversation_id": conversation_id, "memory": razzy_service.recall(conversation_id)})

    return app

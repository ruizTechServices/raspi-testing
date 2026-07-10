from __future__ import annotations

import json

from flask import Blueprint, Response, jsonify, request, stream_with_context

from unified_server.security import require_api_key


def build_gio_blueprint(gio_service) -> Blueprint:
    bp = Blueprint("gio", __name__)

    @bp.get("/api/gio/models")
    @require_api_key
    def gio_models():
        try:
            return jsonify(gio_service.list_models())
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.post("/api/gio/session")
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

    @bp.get("/api/gio/conversations")
    @require_api_key
    def gio_conversations():
        try:
            gio_service.ensure_schema()
            return jsonify({"conversations": gio_service.list_conversations()})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @bp.get("/api/gio/conversations/<conversation_id>/messages")
    @require_api_key
    def gio_messages(conversation_id: str):
        try:
            gio_service.ensure_schema()
            return jsonify({"conversation_id": conversation_id, "messages": gio_service.get_messages(conversation_id)})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @bp.patch("/api/gio/conversations/<conversation_id>")
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

    @bp.delete("/api/gio/conversations/<conversation_id>")
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

    @bp.get("/api/gio/dreams")
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

    @bp.get("/api/gio/dreams/<dream_id>")
    @require_api_key
    def gio_get_dream(dream_id: str):
        try:
            gio_service.ensure_schema()
            return jsonify(gio_service.get_dream(dream_id))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @bp.post("/api/gio/conversations/<conversation_id>/dream")
    @require_api_key
    def gio_create_dream(conversation_id: str):
        try:
            gio_service.ensure_schema()
            return jsonify(gio_service.create_dream(conversation_id)), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @bp.post("/api/gio/chat")
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

    @bp.post("/api/gio/chat/stream")
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

    return bp

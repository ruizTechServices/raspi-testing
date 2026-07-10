from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, jsonify, request

from unified_server.security import require_api_key


def build_chat_blueprint(service) -> Blueprint:
    bp = Blueprint("chat", __name__)

    @bp.get("/api/providers")
    def list_providers():
        return jsonify({"providers": service.providers.list_providers()})

    @bp.post("/api/conversations")
    @require_api_key
    def create_conversation():
        data = request.get_json(silent=True) or {}
        title = data.get("title", "New Chat")
        conversation_id = service.create_conversation(title=title)
        return jsonify({"conversation_id": conversation_id, "title": title})

    @bp.get("/api/conversations")
    @require_api_key
    def list_conversations():
        items = [asdict(item) for item in service.list_conversations()]
        return jsonify({"conversations": items})

    @bp.get("/api/conversations/<conversation_id>/messages")
    @require_api_key
    def get_messages(conversation_id: str):
        try:
            items = [asdict(item) for item in service.get_messages(conversation_id)]
            return jsonify({"conversation_id": conversation_id, "messages": items})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.patch("/api/conversations/<conversation_id>")
    @require_api_key
    def rename_conversation(conversation_id: str):
        data = request.get_json(silent=True) or {}
        title = data.get("title", "")
        try:
            return jsonify(service.rename_conversation(conversation_id, title))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.delete("/api/conversations/<conversation_id>")
    @require_api_key
    def delete_conversation(conversation_id: str):
        try:
            service.delete_conversation(conversation_id)
            return jsonify({"ok": True, "conversation_id": conversation_id})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.post("/api/chat")
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

    return bp

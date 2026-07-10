from __future__ import annotations

from flask import Blueprint, jsonify

from unified_server.security import require_api_key


def build_razzy_blueprint(razzy_service) -> Blueprint:
    """Razzy is profile-only on the web; chat happens through WhatsApp.

    The old chat/memory endpoints stay registered as 410 Gone so existing
    clients get an explicit removal notice instead of a 404.
    """
    bp = Blueprint("razzy", __name__)

    @bp.get("/api/razzy/profile")
    def razzy_profile():
        return jsonify({"profile": razzy_service.profile()})

    @bp.post("/api/razzy/session")
    @require_api_key
    def razzy_session():
        return jsonify({"error": "Razzy chat has been removed from this page."}), 410

    @bp.post("/api/razzy/chat")
    @require_api_key
    def razzy_chat():
        return jsonify({"error": "Razzy chat has been removed from this page."}), 410

    @bp.post("/api/razzy/remember")
    @require_api_key
    def razzy_remember():
        return jsonify({"error": "Razzy chat memory has been removed from this page."}), 410

    @bp.get("/api/razzy/memory/<conversation_id>")
    @require_api_key
    def razzy_memory(conversation_id: str):
        return jsonify({"error": "Razzy chat memory has been removed from this page."}), 410

    return bp

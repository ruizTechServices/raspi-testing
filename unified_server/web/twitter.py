from __future__ import annotations

from flask import Blueprint, jsonify, request

from unified_server.security import require_api_key
from unified_server.twitter.service import TwitterClientConfigError, TwitterClientError


def build_twitter_blueprint(twitter_service) -> Blueprint:
    bp = Blueprint("twitter", __name__)

    @bp.get("/api/twitter/status")
    @require_api_key
    def twitter_status():
        return jsonify({"twitter": twitter_service.status()})

    @bp.get("/api/twitter/me")
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

    @bp.get("/api/twitter/posts/<post_id>")
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

    @bp.get("/api/twitter/timeline/user/<user_id>")
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

    @bp.post("/api/twitter/post")
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

    @bp.post("/api/twitter/posts/<post_id>/reply")
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

    @bp.post("/api/twitter/posts/<post_id>/quote")
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

    @bp.delete("/api/twitter/posts/<post_id>")
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

    return bp

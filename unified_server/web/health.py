from __future__ import annotations

from flask import Blueprint, jsonify


def build_health_blueprint() -> Blueprint:
    bp = Blueprint("health", __name__)

    @bp.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return bp

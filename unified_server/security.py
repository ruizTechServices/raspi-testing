from __future__ import annotations

import secrets
from functools import wraps

from flask import jsonify, request

from unified_server import config


def require_api_key(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        if not config.API_KEY:
            return func(*args, **kwargs)
        supplied = request.headers.get("X-API-Key", "")
        if not supplied or not secrets.compare_digest(supplied, config.API_KEY):
            return jsonify({"error": "Unauthorized"}), 401
        return func(*args, **kwargs)
    return wrapped


def attach_security_headers(app):
    @app.after_request
    def add_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        return response

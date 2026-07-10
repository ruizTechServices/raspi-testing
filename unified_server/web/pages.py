from __future__ import annotations

from pathlib import Path

from flask import Blueprint, send_file

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def build_pages_blueprint() -> Blueprint:
    bp = Blueprint("pages", __name__)

    @bp.get("/")
    def index_ui():
        return send_file(STATIC_DIR / "index.html")

    @bp.get("/console")
    def console_ui():
        return send_file(STATIC_DIR / "console.html")

    @bp.get("/razzy")
    def razzy_ui():
        return send_file(STATIC_DIR / "razzy.html")

    @bp.get("/gio")
    def gio_ui():
        return send_file(STATIC_DIR / "gio.html")

    @bp.get("/gio/dreams")
    def gio_dreams_ui():
        return send_file(STATIC_DIR / "gio-dreams.html")

    return bp

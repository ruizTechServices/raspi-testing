from __future__ import annotations

from flask import Flask

from unified_server.web.chat import build_chat_blueprint
from unified_server.web.gio import build_gio_blueprint
from unified_server.web.health import build_health_blueprint
from unified_server.web.integrations import build_integrations_blueprint
from unified_server.web.pages import build_pages_blueprint
from unified_server.web.razzy import build_razzy_blueprint
from unified_server.web.system import build_system_blueprint
from unified_server.web.twitter import build_twitter_blueprint


def register_blueprints(app: Flask, *, service, razzy_service, twitter_service, gio_service) -> None:
    """Register every feature blueprint. Routes keep their literal paths (no url_prefix)."""
    app.register_blueprint(build_health_blueprint())
    app.register_blueprint(build_system_blueprint())
    app.register_blueprint(build_chat_blueprint(service))
    app.register_blueprint(build_gio_blueprint(gio_service))
    app.register_blueprint(build_twitter_blueprint(twitter_service))
    app.register_blueprint(build_razzy_blueprint(razzy_service))
    app.register_blueprint(build_integrations_blueprint())
    app.register_blueprint(build_pages_blueprint())

from __future__ import annotations

from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from unified_server.database import init_db
from unified_server.gio_service import GioService
from unified_server.razzy_service import RazzyService
from unified_server.security import attach_security_headers
from unified_server.service import ChatService
from unified_server.settings import get_settings
from unified_server.twitter_service import TwitterService
from unified_server.web import register_blueprints


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

    register_blueprints(
        app,
        service=service or ChatService(),
        razzy_service=razzy_service or RazzyService(),
        twitter_service=twitter_service or TwitterService(),
        gio_service=gio_service or GioService(),
    )
    return app

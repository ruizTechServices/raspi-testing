from waitress import serve

from unified_server.app_factory import create_app
from unified_server.settings import get_settings

app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    if settings.APP_RUNNER == "flask":
        app.run(host=settings.HOST, port=settings.PORT, debug=settings.DEBUG, use_reloader=settings.USE_RELOADER)
    else:
        serve(app, host=settings.HOST, port=settings.PORT, threads=settings.WAITRESS_THREADS)

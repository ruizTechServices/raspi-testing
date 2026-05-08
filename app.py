from waitress import serve

from unified_server.app_factory import create_app
from unified_server.config import APP_RUNNER, DEBUG, HOST, PORT, USE_RELOADER, WAITRESS_THREADS

app = create_app()


if __name__ == "__main__":
    if APP_RUNNER == "flask":
        app.run(host=HOST, port=PORT, debug=DEBUG, use_reloader=USE_RELOADER)
    else:
        serve(app, host=HOST, port=PORT, threads=WAITRESS_THREADS)

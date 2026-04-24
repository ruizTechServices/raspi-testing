from unified_server.app_factory import create_app
from unified_server.config import HOST, PORT

app = create_app()


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=True)

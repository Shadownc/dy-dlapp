from .app import create_app
from .settings import load_settings

if __name__ == "__main__":
    settings = load_settings()
    create_app(settings).run(host=settings.host, port=settings.port, threaded=True)

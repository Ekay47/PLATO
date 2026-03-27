from src.core.settings_loader import settings
from src.bootstrap.app_factory import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.get_str("server.host", "127.0.0.1"),
        port=settings.get_int("server.port", 8147),
    )

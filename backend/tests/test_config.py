from app.core.config import Settings


def test_cors_origins_accept_comma_separated_string(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, https://repinspect.dev")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://localhost:5173", "https://repinspect.dev"]


def test_docs_hidden_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    try:
        client_app = create_app()
        assert client_app.docs_url is None
        assert client_app.openapi_url is None
    finally:
        get_settings.cache_clear()

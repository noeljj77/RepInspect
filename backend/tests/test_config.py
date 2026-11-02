import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cors_origins_accept_comma_separated_string(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, https://repinspect.dev")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://localhost:5173", "https://repinspect.dev"]


def test_short_jwt_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "too-short")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_missing_jwt_secret_is_rejected(monkeypatch):
    monkeypatch.delenv("JWT_SECRET")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_development_secret_is_rejected_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "dev-only-secret-do-not-use-in-production-0000")

    with pytest.raises(ValidationError, match="development placeholder"):
        Settings(_env_file=None)


def test_cookie_is_https_only_in_production(monkeypatch):
    assert Settings(_env_file=None).cookie_secure is False

    monkeypatch.setenv("APP_ENV", "production")
    assert Settings(_env_file=None).cookie_secure is True


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

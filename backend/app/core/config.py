"""Application settings loaded from environment variables (and backend/.env)."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Prefix of the throwaway secret shipped in .env.example. It is fine for local
# development but must never be accepted in production.
DEV_SECRET_PREFIX = "dev-only"


# backend/.env, found relative to this file so the app starts correctly no
# matter which directory it is launched from.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "RepInspect"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://repinspect:repinspect@localhost:5433/repinspect"

    # NoDecode stops pydantic-settings from expecting JSON, so a plain
    # comma-separated string works in .env files.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # Required: there is deliberately no default, so a missing secret fails at
    # startup instead of silently signing tokens with a guessable key.
    jwt_secret: SecretStr = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=60 * 24 * 7, gt=0)
    session_cookie_name: str = "repinspect_session"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def reject_dev_secret_in_production(self) -> "Settings":
        if self.app_env == "production" and self.jwt_secret.get_secret_value().startswith(
            DEV_SECRET_PREFIX
        ):
            raise ValueError("JWT_SECRET is still the development placeholder")
        return self

    @property
    def cookie_secure(self) -> bool:
        """Send the session cookie over HTTPS only in production."""
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

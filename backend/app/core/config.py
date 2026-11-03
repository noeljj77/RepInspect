"""Application settings loaded from environment variables (and backend/.env)."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Prefix of the throwaway secret shipped in .env.example. It is fine for local
# development but must never be accepted in production.
DEV_SECRET_PREFIX = "dev-only"


BACKEND_DIR = Path(__file__).resolve().parents[2]
# backend/.env, found relative to this file so the app starts correctly no
# matter which directory it is launched from.
ENV_FILE = BACKEND_DIR / ".env"

MB = 1024 * 1024


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

    # Failed logins are counted per email and per IP address; past the limit, further
    # attempts get 429 until the oldest failure leaves the window. The per-IP limit is
    # higher so one shared address (a school, an office) is not locked out by one typo.
    login_max_failures_per_email: int = Field(default=5, gt=0)
    login_max_failures_per_ip: int = Field(default=30, gt=0)
    login_window_seconds: int = Field(default=15 * 60, gt=0)
    # Behind a reverse proxy every request comes from the proxy's address. Set this only
    # when the proxy overwrites X-Forwarded-For (the bundled nginx config does).
    trust_proxy_headers: bool = False

    # --- GitHub ingestion -------------------------------------------------
    # Optional. Without a token GitHub allows 60 API requests per hour; with one, 5000.
    github_token: SecretStr | None = None
    github_timeout_seconds: float = Field(default=10.0, gt=0)

    # Compressed download size limit (the tarball as sent by GitHub).
    max_download_bytes: int = 50 * MB
    # Largest ZIP file a person may upload.
    max_upload_bytes: int = 50 * MB
    # Total uncompressed size the extractor will read through before giving up.
    # This is what stops a small archive that expands to gigabytes (a "zip bomb").
    max_archive_scan_bytes: int = 500 * MB
    max_files: int = Field(default=5000, gt=0)  # files kept per analysis
    max_file_bytes: int = 1 * MB  # larger files are skipped
    max_total_bytes: int = 100 * MB  # total of kept files
    max_listed_skipped_files: int = 5000  # skipped files recorded individually

    # Where filtered source snapshots are stored (later also FAISS indexes).
    artifact_dir: Path = BACKEND_DIR / "data" / "artifacts"

    # Analyses run in background threads inside the API process.
    analysis_workers: int = Field(default=2, gt=0)
    max_active_analyses_per_user: int = Field(default=3, gt=0)

    # --- AI explanations ---------------------------------------------------
    # The provider is chosen here so another one can be added without touching the
    # features that use it. "none" switches the AI features off.
    llm_provider: Literal["gemini", "none"] = "gemini"
    gemini_api_key: SecretStr | None = None
    llm_model: str = "gemini-3.5-flash-lite"
    llm_timeout_seconds: float = Field(default=90.0, gt=0)
    # Attempts per request, counting the first. Covers temporary errors such as
    # "model is busy" (503), which the free tier returns during demand spikes.
    llm_max_attempts: int = Field(default=3, ge=1, le=6)
    # How much repository material goes into one prompt (characters, roughly 4 per token).
    # Whole repositories are never sent: only a selection of facts and excerpts.
    ai_context_chars: int = Field(default=60_000, ge=5_000)
    # Free tiers have small quotas, so each person gets a daily allowance.
    max_ai_requests_per_user_per_day: int = Field(default=40, gt=0)
    max_active_ai_jobs_per_user: int = Field(default=2, gt=0)

    # --- Chat over the code (retrieval-augmented generation) ----------------
    # A small embedding model that runs locally on the CPU, so indexing costs nothing
    # and repository code is not sent anywhere to be embedded. Downloaded on first use.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # BGE models expect this instruction in front of search queries (not documents).
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "
    embedding_batch_size: int = Field(default=32, gt=0)
    # Tokens of each chunk the model reads. 256 instead of the model's 512 is about 1.5x
    # faster with nearly identical vectors: a chunk's first lines carry most of its meaning.
    embedding_max_tokens: int = Field(default=256, ge=32, le=512)
    model_cache_dir: Path = BACKEND_DIR / "data" / "models"
    # Code chunks kept per analysis. Very large repositories are indexed up to this.
    max_chunks_per_analysis: int = Field(default=20_000, gt=0)
    # How many excerpts an answer may use, and how much text they may take in total.
    rag_top_k: int = Field(default=8, gt=0, le=30)
    rag_context_chars: int = Field(default=24_000, ge=4_000)
    # Earlier questions and answers sent along, so follow-up questions make sense.
    chat_history_turns: int = Field(default=3, ge=0, le=10)

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
    def gemini_key(self) -> str | None:
        """The Gemini key, or None when it is unset or blank (GEMINI_API_KEY= in .env)."""
        if self.gemini_api_key is None:
            return None
        return self.gemini_api_key.get_secret_value().strip() or None

    @property
    def llm_configured(self) -> bool:
        return self.llm_provider == "gemini" and self.gemini_key is not None

    @property
    def cookie_secure(self) -> bool:
        """Send the session cookie over HTTPS only in production."""
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

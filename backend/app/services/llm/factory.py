from app.core.config import Settings, get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.errors import LLMNotConfigured
from app.services.llm.gemini import GeminiProvider


def create_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Build the provider chosen in settings. Raises LLMNotConfigured if none is usable."""
    settings = settings or get_settings()
    key = settings.gemini_key
    if settings.llm_provider == "gemini" and key is not None:
        return GeminiProvider(
            api_key=key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
            max_attempts=settings.llm_max_attempts,
        )
    raise LLMNotConfigured("AI explanations are not set up on this server.")

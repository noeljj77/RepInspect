"""Failures when talking to a language model.

`message` is written for end users and never contains prompts, keys or raw provider
responses. `code` is stable and stored on failed explanations.
"""


class LLMError(Exception):
    code = "ai_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class LLMNotConfigured(LLMError):
    code = "ai_not_configured"


class LLMUnavailable(LLMError):
    """The provider is busy, down or unreachable. Retrying later usually works."""

    code = "ai_unavailable"


class LLMRateLimited(LLMError):
    """Too many requests per minute. Waiting a little fixes it."""

    code = "ai_rate_limited"

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class LLMQuotaExhausted(LLMError):
    """The daily allowance is used up. Retrying within the hour will not help."""

    code = "ai_quota_exhausted"


class LLMBadResponse(LLMError):
    """The model answered, but not with usable output (invalid JSON, cut off...)."""

    code = "ai_bad_response"


class LLMBlocked(LLMError):
    """The provider's safety system declined to answer."""

    code = "ai_blocked"

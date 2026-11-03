"""A small in-memory limiter for failed attempts, such as wrong passwords.

State lives in this process only. That is enough for the single-process deployment
this app is built for; running several workers would multiply the allowance, and
a shared store such as Redis would be the next step.
"""

import threading
import time
from collections import deque

from fastapi import Request

from app.core.config import Settings

# Keys are emails and IP addresses chosen by the caller, so the table is capped.
MAX_KEYS = 10_000


class FailureLimiter:
    def __init__(self, *, max_failures: int, window_seconds: float) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> int:
        """Seconds until another attempt is allowed, or 0 when one is allowed now."""
        with self._lock:
            failures = self._recent(key, time.monotonic())
            if len(failures) < self.max_failures:
                return 0
            return max(1, int(failures[0] + self.window - time.monotonic()) + 1)

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            if key not in self._failures and len(self._failures) >= MAX_KEYS:
                self._drop_expired(now)
                if len(self._failures) >= MAX_KEYS:
                    return  # under a flood of distinct keys, keep what we have
            self._failures.setdefault(key, deque()).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def _recent(self, key: str, now: float) -> deque[float]:
        failures = self._failures.get(key)
        if failures is None:
            return deque()
        while failures and failures[0] <= now - self.window:
            failures.popleft()
        if not failures:
            del self._failures[key]
        return failures

    def _drop_expired(self, now: float) -> None:
        for key in list(self._failures):
            self._recent(key, now)


class LoginLimits:
    """The two limiters a login passes through."""

    def __init__(self, settings: Settings) -> None:
        window = settings.login_window_seconds
        self.by_email = FailureLimiter(
            max_failures=settings.login_max_failures_per_email, window_seconds=window
        )
        self.by_ip = FailureLimiter(
            max_failures=settings.login_max_failures_per_ip, window_seconds=window
        )


def client_ip(request: Request, *, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        # The last entry is the one the nearest proxy added; earlier ones can be forged.
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[-1].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"

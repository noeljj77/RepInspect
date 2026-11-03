from app.core import rate_limit
from app.core.rate_limit import FailureLimiter


def test_allows_attempts_until_the_limit_then_reports_the_wait(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])
    limiter = FailureLimiter(max_failures=2, window_seconds=60)

    limiter.record_failure("a")
    assert limiter.retry_after("a") == 0
    limiter.record_failure("a")

    assert 0 < limiter.retry_after("a") <= 61
    assert limiter.retry_after("b") == 0


def test_failures_expire_after_the_window(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])
    limiter = FailureLimiter(max_failures=1, window_seconds=60)
    limiter.record_failure("a")
    assert limiter.retry_after("a") > 0

    now[0] += 61

    assert limiter.retry_after("a") == 0


def test_reset_forgets_a_key():
    limiter = FailureLimiter(max_failures=1, window_seconds=60)
    limiter.record_failure("a")
    limiter.reset("a")

    assert limiter.retry_after("a") == 0


def test_the_table_of_keys_is_capped(monkeypatch):
    monkeypatch.setattr(rate_limit, "MAX_KEYS", 3)
    limiter = FailureLimiter(max_failures=1, window_seconds=60)

    for key in "abcdef":
        limiter.record_failure(key)

    assert len(limiter._failures) == 3

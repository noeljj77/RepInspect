import json

import httpx
import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.services.llm.errors import (
    LLMBadResponse,
    LLMBlocked,
    LLMNotConfigured,
    LLMQuotaExhausted,
    LLMRateLimited,
    LLMUnavailable,
)
from app.services.llm.factory import create_llm_provider
from app.services.llm.gemini import GeminiProvider

KEY = "AIzaSy-test-key-that-must-never-leak-0123456789"


class Answer(BaseModel):
    text: str
    score: int


def ok(text: str, **extra) -> httpx.Response:
    body = {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 7},
    }
    body.update(extra)
    return httpx.Response(200, json=body)


def error(http_status: int, **error_fields) -> httpx.Response:
    return httpx.Response(http_status, json={"error": {"code": http_status, **error_fields}})


class Script:
    """A fake Gemini that answers requests from a list, and records what it was sent."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def bodies(self):
        return [json.loads(r.content) for r in self.requests]


def provider(script, *, attempts=3, sleeps=None) -> GeminiProvider:
    return GeminiProvider(
        api_key=KEY,
        model="test-model",
        max_attempts=attempts,
        transport=httpx.MockTransport(script),
        sleep=(sleeps.append if sleeps is not None else (lambda _: None)),
    )


def run(p: GeminiProvider):
    return p.generate_structured(system="SYS", prompt="PROMPT", schema=Answer)


GOOD = json.dumps({"text": "hello", "score": 3})


# --- the request ---------------------------------------------------------------------------------


def test_success_returns_validated_data_and_token_counts():
    script = Script(ok(GOOD))

    result = run(provider(script))

    assert result.data == Answer(text="hello", score=3)
    assert (result.model, result.input_tokens, result.output_tokens) == ("test-model", 11, 7)


def test_request_asks_for_json_matching_the_schema():
    script = Script(ok(GOOD))
    run(provider(script))

    [request] = script.requests
    body = script.bodies()[0]
    assert request.url.path.endswith("/models/test-model:generateContent")
    assert body["systemInstruction"]["parts"][0]["text"] == "SYS"
    assert body["contents"][0]["parts"][0]["text"] == "PROMPT"
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert set(config["responseJsonSchema"]["properties"]) == {"text", "score"}
    assert config["maxOutputTokens"] == 4096


def test_the_key_is_sent_in_a_header_and_never_in_the_url():
    script = Script(ok(GOOD))
    run(provider(script))

    [request] = script.requests
    assert request.headers["x-goog-api-key"] == KEY
    assert KEY not in str(request.url)


# --- temporary failures are retried ------------------------------------------------------------------


def test_a_busy_model_is_retried_with_growing_pauses():
    sleeps: list[float] = []
    script = Script(error(503), error(503), ok(GOOD))

    result = run(provider(script, sleeps=sleeps))

    assert result.data.text == "hello"
    assert len(script.requests) == 3
    assert len(sleeps) == 2 and 1 <= sleeps[0] < 2 and 2 <= sleeps[1] < 3


def test_giving_up_after_the_last_attempt_reports_unavailable():
    sleeps: list[float] = []
    script = Script(error(503), error(500), error(503))

    with pytest.raises(LLMUnavailable, match="busy"):
        run(provider(script, sleeps=sleeps))

    assert len(script.requests) == 3 and len(sleeps) == 2  # no pause after the final failure


def test_the_provider_asks_for_a_pause_the_service_requests():
    sleeps: list[float] = []
    details = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "7s"}]
    script = Script(error(429, status="RESOURCE_EXHAUSTED", details=details), ok(GOOD))

    run(provider(script, sleeps=sleeps))

    assert sleeps == [7.5]


def test_a_very_long_requested_pause_is_capped():
    sleeps: list[float] = []
    details = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "600s"}]
    script = Script(error(429, details=details), ok(GOOD))

    run(provider(script, sleeps=sleeps))

    assert sleeps == [30.0]


def test_a_per_minute_limit_that_never_clears_reports_rate_limited():
    script = Script(error(429), error(429), error(429))

    with pytest.raises(LLMRateLimited):
        run(provider(script))


@pytest.mark.parametrize("exception", [httpx.ReadTimeout("slow"), httpx.ConnectError("down")])
def test_timeouts_and_connection_failures_are_retried(exception):
    script = Script(exception, ok(GOOD))

    assert run(provider(script)).data.text == "hello"
    assert len(script.requests) == 2


def test_persistent_timeouts_report_unavailable():
    script = Script(*[httpx.ReadTimeout("slow")] * 3)

    with pytest.raises(LLMUnavailable, match="too long"):
        run(provider(script))


# --- permanent failures are not retried -----------------------------------------------------------------


def test_a_used_up_daily_quota_is_not_retried():
    details = [
        {
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
        }
    ]
    script = Script(error(429, status="RESOURCE_EXHAUSTED", details=details))

    with pytest.raises(LLMQuotaExhausted, match="tomorrow"):
        run(provider(script))

    assert len(script.requests) == 1


@pytest.mark.parametrize("status", [401, 403])
def test_a_rejected_key_is_reported_clearly_and_not_retried(status):
    script = Script(error(status, message="API key not valid"))

    with pytest.raises(LLMNotConfigured, match="key was rejected"):
        run(provider(script))

    assert len(script.requests) == 1


def test_an_unknown_model_is_reported_clearly():
    with pytest.raises(LLMNotConfigured, match="test-model"):
        run(provider(Script(error(404))))


def test_a_rejected_request_is_reported_without_the_providers_message():
    script = Script(error(400, message="Invalid JSON payload: secret-looking details"))

    with pytest.raises(LLMBadResponse) as caught:
        run(provider(script))

    assert "secret-looking" not in caught.value.message
    assert len(script.requests) == 1


# --- bad output ------------------------------------------------------------------------------------------


def test_invalid_json_gets_one_chance_to_be_corrected_with_the_error_explained():
    script = Script(ok("this is not json"), ok(GOOD))

    result = run(provider(script))

    assert result.data.score == 3
    second = script.bodies()[1]["contents"]
    assert [turn["role"] for turn in second] == ["user", "model", "user"]
    assert second[1]["parts"][0]["text"] == "this is not json"
    assert "not valid for the required JSON format" in second[2]["parts"][0]["text"]


def test_output_that_does_not_fit_the_schema_is_corrected_the_same_way():
    wrong = json.dumps({"text": "hello", "score": "not a number"})
    script = Script(ok(wrong), ok(GOOD))

    run(provider(script))

    assert "score" in script.bodies()[1]["contents"][2]["parts"][0]["text"]


def test_two_bad_answers_in_a_row_fail():
    script = Script(ok("nope"), ok("still nope"))

    with pytest.raises(LLMBadResponse, match="wrong format"):
        run(provider(script))

    assert len(script.requests) == 2


def test_a_correction_attempt_does_not_reset_retry_accounting_for_outages():
    script = Script(ok("nope"), error(503), ok(GOOD))

    assert run(provider(script, attempts=2)).data.text == "hello"


@pytest.mark.parametrize(
    ("payload", "expected", "message"),
    [
        (
            {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{"}]}}]},
            LLMBadResponse,
            "cut off",
        ),
        ({"candidates": [{"finishReason": "SAFETY"}]}, LLMBlocked, "declined"),
        ({"candidates": [{"finishReason": "PROHIBITED_CONTENT"}]}, LLMBlocked, "declined"),
        ({"promptFeedback": {"blockReason": "SAFETY"}}, LLMBlocked, "declined"),
        ({"candidates": []}, LLMBadResponse, "no answer"),
        ({}, LLMBadResponse, "no answer"),
        (
            {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "  "}]}}]},
            LLMBadResponse,
            "empty",
        ),
    ],
)
def test_unusable_answers_are_reported_specifically(payload, expected, message):
    script = Script(httpx.Response(200, json=payload))

    with pytest.raises(expected, match=message):
        run(provider(script))


def test_the_models_thinking_text_is_ignored():
    parts = [{"text": "internal reasoning", "thought": True}, {"text": GOOD}]
    script = Script(
        httpx.Response(
            200, json={"candidates": [{"content": {"parts": parts}, "finishReason": "STOP"}]}
        )
    )

    assert run(provider(script)).data.text == "hello"


def test_no_error_message_ever_contains_the_key():
    failures = [error(401), error(403), error(404), error(429), error(400), error(503)]
    for failure in failures:
        with pytest.raises(Exception) as caught:  # noqa: PT011
            run(provider(Script(failure, failure, failure)))
        assert KEY not in str(caught.value)


# --- settings and factory ---------------------------------------------------------------------------------


def settings(**overrides) -> Settings:
    # The test environment switches AI off by default, so ask for Gemini explicitly.
    return Settings(_env_file=None, **{"llm_provider": "gemini", **overrides})


def test_the_factory_builds_gemini_from_settings():
    built = create_llm_provider(settings(gemini_api_key=KEY, llm_model="some-model"))

    assert isinstance(built, GeminiProvider) and built.model == "some-model"


@pytest.mark.parametrize(
    "overrides",
    [{"gemini_api_key": None}, {"llm_provider": "none", "gemini_api_key": KEY}],
)
def test_the_factory_refuses_when_ai_is_not_set_up(overrides):
    with pytest.raises(LLMNotConfigured, match="not set up"):
        create_llm_provider(settings(**overrides))


def test_llm_configured_reflects_the_settings():
    assert settings(gemini_api_key=KEY).llm_configured is True
    assert settings().llm_configured is False
    assert settings(gemini_api_key="  ").llm_configured is False
    assert settings(llm_provider="none", gemini_api_key=KEY).llm_configured is False


def test_the_key_is_not_shown_when_settings_are_printed():
    assert KEY not in repr(settings(gemini_api_key=KEY))

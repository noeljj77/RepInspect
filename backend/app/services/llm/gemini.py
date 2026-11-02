"""Google Gemini through its REST API.

Uses httpx directly (already a dependency) instead of an SDK. Properties:
- The API key travels in a header, never in the URL, so request logging cannot leak it.
- Structured output: the Pydantic schema is sent as `responseJsonSchema`, and the reply is
  validated again here because a model can still produce something that does not fit.
- Temporary failures (busy model, timeouts, per-minute limits) are retried with backoff.
  A used-up daily quota is not retried, because waiting a few seconds cannot fix it.
- Prompts and replies are never logged, only the model, status codes and token counts.
"""

import logging
import random
import re
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import ValidationError

from app.services.llm.base import LLMResult, T
from app.services.llm.errors import (
    LLMBadResponse,
    LLMBlocked,
    LLMError,
    LLMNotConfigured,
    LLMQuotaExhausted,
    LLMRateLimited,
    LLMUnavailable,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MAX_RETRY_WAIT_SECONDS = 30.0
_BLOCKED_FINISH_REASONS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "IMAGE_SAFETY"}


class GeminiProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float = 90.0,
        max_attempts: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.model = model
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=BASE_URL,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            timeout=httpx.Timeout(timeout, connect=10.0),
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    # --- public API ---------------------------------------------------------------

    def generate_structured(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[T],
        max_output_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResult[T]:
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema.model_json_schema(),
                "maxOutputTokens": max_output_tokens,
                "temperature": temperature,
            },
        }

        format_retry_used = False
        while True:
            payload = self._send_with_retries(body)
            text, input_tokens, output_tokens = self._extract_text(payload)
            try:
                data = schema.model_validate_json(text)
            except ValidationError as error:
                if format_retry_used:
                    raise LLMBadResponse(
                        "The AI returned an answer in the wrong format. Try again."
                    ) from None
                # Give the model one chance to fix its own mistake, telling it what was wrong
                # (the error describes the schema, not the repository, so it is safe to echo).
                format_retry_used = True
                logger.warning(
                    "Gemini reply did not match the schema (%d errors)", error.error_count()
                )
                contents.append({"role": "model", "parts": [{"text": text[:6000]}]})
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": "That reply was not valid for the required JSON format: "
                                + _summarize_validation_error(error)
                                + " Reply again with only the corrected JSON."
                            }
                        ],
                    }
                )
                continue
            return LLMResult(data, self.model, input_tokens, output_tokens)

    # --- internals ----------------------------------------------------------------

    def _send_with_retries(self, body: dict[str, Any]) -> dict[str, Any]:
        last_error: LLMError | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._http.post(f"/models/{self.model}:generateContent", json=body)
            except httpx.TimeoutException:
                last_error = LLMUnavailable("The AI took too long to respond. Try again.")
            except httpx.HTTPError:
                last_error = LLMUnavailable("Could not reach the AI service. Try again.")
            else:
                outcome = self._interpret(response)
                if isinstance(outcome, dict):
                    return outcome
                last_error = outcome

            if attempt == self._max_attempts or not _is_temporary(last_error):
                raise last_error
            wait = self._wait_time(last_error, attempt)
            logger.info("AI request failed (%s); retrying in %.1fs", last_error.code, wait)
            self._sleep(wait)
        raise last_error  # pragma: no cover  (the loop always returns or raises)

    @staticmethod
    def _wait_time(error: LLMError, attempt: int) -> float:
        if isinstance(error, LLMRateLimited) and error.retry_after is not None:
            return min(error.retry_after + 0.5, MAX_RETRY_WAIT_SECONDS)
        # 1s, 2s, 4s... with jitter so simultaneous retries do not collide again.
        return min(2 ** (attempt - 1) + random.uniform(0, 0.5), MAX_RETRY_WAIT_SECONDS)

    def _interpret(self, response: httpx.Response) -> dict[str, Any] | LLMError:
        status = response.status_code
        if status == 200:
            return response.json()

        logger.warning("Gemini %s returned HTTP %d", self.model, status)
        detail = _error_detail(response)
        if status in (401, 403):
            return LLMNotConfigured("The AI key was rejected. Check GEMINI_API_KEY.")
        if status == 429:
            if detail["daily_quota"]:
                return LLMQuotaExhausted(
                    "The daily AI allowance has been used up. Try again tomorrow."
                )
            return LLMRateLimited(
                "The AI is receiving too many requests. Try again in a minute.",
                retry_after=detail["retry_after"],
            )
        if status in (500, 502, 503, 504):
            return LLMUnavailable("The AI service is busy right now. Try again in a moment.")
        if status == 404:
            return LLMNotConfigured(f"The AI model '{self.model}' was not found. Check LLM_MODEL.")
        return LLMBadResponse("The AI service rejected the request.")

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> tuple[str, int | None, int | None]:
        usage = payload.get("usageMetadata") or {}
        feedback = payload.get("promptFeedback") or {}
        if feedback.get("blockReason"):
            raise LLMBlocked("The AI declined to analyze this content.")

        candidates = payload.get("candidates") or []
        if not candidates:
            raise LLMBadResponse("The AI returned no answer. Try again.")
        candidate = candidates[0]
        reason = candidate.get("finishReason")
        if reason in _BLOCKED_FINISH_REASONS:
            raise LLMBlocked("The AI declined to analyze this content.")
        if reason == "MAX_TOKENS":
            raise LLMBadResponse("The AI's answer was cut off because it was too long. Try again.")

        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
        if not text.strip():
            raise LLMBadResponse("The AI returned an empty answer. Try again.")
        return text, usage.get("promptTokenCount"), usage.get("candidatesTokenCount")


def _is_temporary(error: LLMError) -> bool:
    return isinstance(error, LLMUnavailable | LLMRateLimited)


def _error_detail(response: httpx.Response) -> dict[str, Any]:
    """Pull the two facts retry logic needs out of a Gemini error body."""
    result: dict[str, Any] = {"daily_quota": False, "retry_after": None}
    try:
        error = response.json().get("error", {})
    except ValueError:
        return result
    for item in error.get("details", []):
        kind = str(item.get("@type", ""))
        if kind.endswith("QuotaFailure"):
            for violation in item.get("violations", []):
                if "PerDay" in str(violation.get("quotaId", "")):
                    result["daily_quota"] = True
        elif kind.endswith("RetryInfo"):
            match = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(item.get("retryDelay", "")))
            if match:
                result["retry_after"] = float(match.group(1))
    return result


def _summarize_validation_error(error: ValidationError) -> str:
    parts = []
    for item in error.errors()[:5]:
        location = ".".join(str(p) for p in item["loc"]) or "reply"
        parts.append(f"{location}: {item['msg']}")
    return "; ".join(parts) + "."

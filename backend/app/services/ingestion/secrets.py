"""Redact secret-looking strings from source text before it is stored or sent to an AI.

This is a safety net, not a guarantee: it catches well-known token formats and quoted
values assigned to names like `password` or `api_key`. Whole files that usually hold
secrets (.env, private keys) are dropped earlier by file_filter.

Redaction never changes the number of lines, so line numbers in citations stay correct.
"""

import re

PLACEHOLDER = "[REDACTED]"

_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL
)

_TOKEN_FORMATS = [
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),  # GitHub tokens
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),  # Slack
    re.compile(r"\b[sr]k_live_[A-Za-z0-9]{16,}\b"),  # Stripe
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),  # Google API key
    re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{32,}\b"),  # OpenAI / Anthropic style keys
]

# name = "value" or name: "value", where the name ends in a secret-like word. There is
# deliberately no word boundary before the keyword, so DB_PASSWORD and stripe_secret_key
# match too (an underscore counts as a word character, which would block `\b`).
_ASSIGNMENT = re.compile(
    r"""((?:api[_-]?key|secret(?:[_-]?key)?|access[_-]?token|auth[_-]?token|"""
    r"""client[_-]?secret|password|passwd|pwd)\b["']?\s*[:=]\s*)(["'])([^"'\s]{8,})\2""",
    re.IGNORECASE,
)

_PLACEHOLDER_WORDS = (
    "example",
    "changeme",
    "change-me",
    "your",
    "xxxx",
    "placeholder",
    "sample",
    "redacted",  # already replaced by an earlier pattern; do not count it twice
)


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return (
        value[0] in "$<{%"  # ${VAR}, <token>, {{ template }}, %s
        or any(word in lowered for word in _PLACEHOLDER_WORDS)
        or len(set(value)) <= 2  # "********", "00000000"
    )


def redact_secrets(text: str) -> tuple[str, int]:
    """Return the text with secrets replaced, and how many were replaced."""
    count = 0

    def replace_block(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        # Keep the same number of lines so later line numbers do not shift.
        return f"{PLACEHOLDER} PRIVATE KEY" + "\n" * match.group(0).count("\n")

    def replace_token(_: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return PLACEHOLDER

    def replace_assignment(match: re.Match[str]) -> str:
        nonlocal count
        value = match.group(3)
        if _looks_like_placeholder(value):
            return match.group(0)
        count += 1
        return f"{match.group(1)}{match.group(2)}{PLACEHOLDER}{match.group(2)}"

    text = _PRIVATE_KEY_BLOCK.sub(replace_block, text)
    for pattern in _TOKEN_FORMATS:
        text = pattern.sub(replace_token, text)
    text = _ASSIGNMENT.sub(replace_assignment, text)
    return text, count

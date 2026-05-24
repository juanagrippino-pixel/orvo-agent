"""Secret/PII redaction helpers for Orvo Brain control-plane artifacts."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SECRET_KEY_PARTS = (
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "authorization",
    "auth_header",
    "password",
    "private_key",
    "credential",
    "cookie",
    "session",
    "signature",
    "secret",
    "token",
)

_BEARER_RE = re.compile(r"Bearer\s+[^\s,;]+", flags=re.IGNORECASE)
_SECRET_KEY_PATTERN = (
    r"access_token|refresh_token|api_key|apikey|authorization|auth_header|password|"
    r"private_key|credential|cookie|session|signature|secret|token"
)
_QUOTED_KEY_VALUE_SECRET_RE = re.compile(
    rf"(?i)([\"']?\b({_SECRET_KEY_PATTERN})\b[\"']?\s*[:=]\s*)([\"'])(.*?)(\3)"
)
_UNQUOTED_KEY_VALUE_SECRET_RE = re.compile(
    rf"(?i)([\"']?\b({_SECRET_KEY_PATTERN})\b[\"']?\s*[:=]\s*)([^\"'\s,;&}}]+)"
)
_PRIVATE_KEY_BLOCK_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    flags=re.DOTALL,
)


def is_secret_key(key: str) -> bool:
    """Return True when a metadata/config key is likely to carry a secret."""

    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SECRET_KEY_PARTS)


def redact_text(value: str | None) -> str | None:
    """Redact common inline secret shapes from text."""

    if value is None:
        return None
    redacted = _PRIVATE_KEY_BLOCK_RE.sub("[REDACTED_PRIVATE_KEY]", value)
    redacted = _BEARER_RE.sub("Bearer [REDACTED]", redacted)
    redacted = _QUOTED_KEY_VALUE_SECRET_RE.sub(
        lambda match: f"{match.group(1)}{match.group(3)}[REDACTED]{match.group(5)}",
        redacted,
    )
    redacted = _UNQUOTED_KEY_VALUE_SECRET_RE.sub(
        lambda match: f"{match.group(1)}[REDACTED]",
        redacted,
    )
    return redacted


def redact_uri(value: str | None) -> str | None:
    """Redact secret-shaped query params from URL/reference strings."""

    redacted = redact_text(value)
    if redacted is None:
        return None
    try:
        parts = urlsplit(redacted)
    except ValueError:
        return redacted
    if not parts.query:
        return redacted

    safe_query = urlencode(
        [
            (key, "[REDACTED]" if is_secret_key(key) else query_value)
            for key, query_value in parse_qsl(parts.query, keep_blank_values=True)
        ],
        doseq=True,
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, safe_query, parts.fragment))


def redact_secrets(value: Any) -> Any:
    """Recursively redact secrets while preserving safe operational identifiers."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            redacted[key] = "[REDACTED]" if is_secret_key(key) else redact_secrets(raw_value)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    if isinstance(value, str):
        return redact_uri(value)
    return value

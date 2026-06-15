"""Connector health taxonomy and lightweight failure classification.

The connector registry contract defines this taxonomy as the stable control-plane
language for connector outcomes. Runtime/ledger code uses these helpers to avoid
inventing ad-hoc health strings outside the registry envelope.
"""

from __future__ import annotations

from typing import Literal, Sequence

ConnectorHealthState = Literal[
    "ok",
    "degraded",
    "stale",
    "unauthorized",
    "rate_limited",
    "failed",
]

CONNECTOR_HEALTH_STATES: tuple[ConnectorHealthState, ...] = (
    "ok",
    "degraded",
    "stale",
    "unauthorized",
    "rate_limited",
    "failed",
)


def default_connector_health_state(status: str) -> ConnectorHealthState:
    """Map lifecycle status to the least-specific connector health state."""

    if status == "succeeded":
        return "ok"
    if status == "skipped":
        return "degraded"
    return "failed"


def classify_connector_failure_health_state(error_summary: str) -> ConnectorHealthState:
    """Classify common connector failure text into registry health states.

    The classifier is intentionally conservative: it only promotes failures into
    typed states when the text includes common non-secret operational markers.
    Unknown failures remain ``failed`` instead of inventing connector-specific
    states not present in the registry taxonomy.
    """

    normalized = error_summary.lower()
    if any(marker in normalized for marker in ("401", "403", "unauthorized", "forbidden")):
        return "unauthorized"
    if any(
        marker in normalized
        for marker in (
            "expired token",
            "invalid token",
            "token expired",
            "credentials revoked",
            "invalid credentials",
            "credential revoked",
        )
    ):
        return "unauthorized"
    if any(
        marker in normalized
        for marker in (
            "429",
            "rate limit",
            "rate_limited",
            "throttle",
            "too many requests",
            "retry after",
            "quota exceeded",
        )
    ):
        return "rate_limited"
    if any(marker in normalized for marker in ("stale", "too old", "outdated")):
        return "stale"
    return "failed"


def classify_connector_failure_detail(
    error_summary: str,
    *,
    detailed_states: Sequence[str] = (),
) -> str | None:
    """Resolve a declared connector-specific failure detail when text matches.

    This never invents new detail labels: it only returns values already declared
    by the connector registry spec passed via ``detailed_states``.
    """

    normalized = error_summary.lower()
    declared = {state for state in detailed_states if isinstance(state, str) and state}
    if not declared:
        return None

    if "malformed_response" in declared and any(
        marker in normalized
        for marker in (
            "malformed response",
            "unexpected response payload",
            "invalid json",
            "json decode",
            "decode error",
            "response parse error",
        )
    ):
        return "malformed_response"

    if "api_server_error" in declared and any(
        marker in normalized
        for marker in (
            "http 500",
            "http 502",
            "http 503",
            "http 504",
            "server error",
            "upstream unavailable",
            "service unavailable",
        )
    ):
        return "api_server_error"

    connection_markers = (
        "timed out",
        "timeout",
        "connection reset",
        "connection refused",
        "connection aborted",
        "network error",
        "temporary failure in name resolution",
        "name resolution",
        "dns",
        "remote disconnected",
    )
    if "network_error" in declared and any(marker in normalized for marker in connection_markers):
        return "network_error"
    if "connection_error" in declared and any(marker in normalized for marker in connection_markers):
        return "connection_error"

    return None

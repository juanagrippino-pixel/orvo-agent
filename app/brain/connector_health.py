"""Connector health taxonomy and lightweight failure classification.

The connector registry contract defines this taxonomy as the stable control-plane
language for connector outcomes. Runtime/ledger code uses these helpers to avoid
inventing ad-hoc health strings outside the registry envelope.
"""

from __future__ import annotations

from typing import Literal

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

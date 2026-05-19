"""Safe runtime environment validation for Orvo Brain.

This module reports whether required runtime variables are present without ever
returning raw secret values. It is intended for health checks, setup scripts, and
operator-facing diagnostics.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, Field


class RuntimeEnvCheck(BaseModel):
    """Result of validating Orvo Brain runtime environment requirements."""

    ready: bool
    configured: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    summary: str


_BASE_REQUIRED = ("WHATSAPP_PHONE_ID", "WHATSAPP_TOKEN")
_CONNECTOR_REQUIRED = {
    "google_sheets": ("GOOGLE_CLIENT_SECRET_FILE", "GOOGLE_OAUTH_TOKEN_FILE"),
    "tiendanube": ("TIENDANUBE_USER_ID", "TIENDANUBE_ACCESS_TOKEN"),
}


def _requirements(connectors: Sequence[str] | None) -> list[str]:
    required: list[str] = list(_BASE_REQUIRED)
    for connector in connectors or []:
        required.extend(_CONNECTOR_REQUIRED.get(connector, ()))
    return list(dict.fromkeys(required))


def check_runtime_env(
    *,
    env: Mapping[str, str] | None = None,
    connectors: Sequence[str] | None = None,
) -> RuntimeEnvCheck:
    """Check required Orvo Brain runtime variables without exposing values.

    Args:
        env: Mapping to inspect. Defaults to ``os.environ``.
        connectors: Optional connector types that add connector-specific vars.

    Returns:
        RuntimeEnvCheck with variable names only. Secret values are never copied
        into the result.
    """

    source = env if env is not None else os.environ
    required = _requirements(connectors)
    configured = [name for name in required if bool(source.get(name))]
    missing = [name for name in required if name not in configured]
    ready = not missing
    if ready:
        summary = f"Runtime env ready: {len(configured)} variable(s) configured."
    else:
        summary = "Runtime env missing required variable(s): " + ", ".join(missing)
    return RuntimeEnvCheck(
        ready=ready,
        configured=configured,
        missing=missing,
        summary=summary,
    )

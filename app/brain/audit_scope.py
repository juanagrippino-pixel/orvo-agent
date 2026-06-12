"""Canonical audit tenant-scope helpers.

Operator audit events persist redacted tenant display identifiers while querying by
a non-secret deterministic scope key. Keeping this logic shared prevents append
and export paths from drifting when a tenant/business identifier contains a
secret-shaped value.
"""

from __future__ import annotations

import hashlib

from app.brain.security.redaction import redact_text


AUDIT_BUSINESS_SCOPE_KEY_VERSION = "audit_business_scope_sha256_v1"


def audit_business_display_id(business_id: str) -> str:
    """Return the tenant identifier safe to persist/export.

    Normal business ids are operational routing labels. If the label contains a
    pasted credential shape, collapse the entire display id instead of
    persisting a partially redacted tenant string such as ``artemea
    token=[REDACTED]``. The raw value remains queryable via
    ``audit_business_scope_key`` only.
    """

    redacted = redact_text(business_id) or "[REDACTED]"
    return redacted if redacted == business_id else "[REDACTED]"


def audit_business_scope_key(business_id: str) -> str:
    """Return a deterministic non-secret lookup key for audit tenant scope."""

    digest = hashlib.sha256(business_id.encode("utf-8")).hexdigest()
    return f"{AUDIT_BUSINESS_SCOPE_KEY_VERSION}:{digest}"

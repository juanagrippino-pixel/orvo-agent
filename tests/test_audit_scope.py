from __future__ import annotations

import hashlib

from app.brain.audit_scope import audit_business_display_id, audit_business_scope_key


def test_audit_scope_collapses_secret_shaped_business_labels_even_when_partially_redacted():
    raw_business_label = "artemea access_token=raw_business_secret"
    partially_redacted_label = "artemea access_token=[REDACTED]"

    assert audit_business_display_id(raw_business_label) == "[REDACTED]"
    assert audit_business_display_id(partially_redacted_label) == "[REDACTED]"


def test_audit_scope_keeps_deterministic_keys_for_normal_business_labels():
    business_id = "artemea"

    assert audit_business_display_id(business_id) == "artemea"
    assert audit_business_scope_key(business_id) == audit_business_scope_key("artemea")
    assert audit_business_scope_key(business_id) == (
        f"audit_business_scope_sha256_v1:"
        f"{hashlib.sha256(business_id.encode('utf-8')).hexdigest()}"
    )

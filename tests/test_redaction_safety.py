from __future__ import annotations

import json

from app.brain.security.redaction import redact_secrets, redact_text


def test_authorization_headers_are_redacted_without_credential_tail_leaks():
    basic_credential = "dGVzdF91c2Vy" + "OnRlc3RfcGFzcw=="
    bearer_token = "bearer_" + "token_value_12345"

    inline = (
        f"upstream failed Authorization: Basic {basic_credential}; "
        f"retry with Authorization: Bearer {bearer_token}"
    )
    redacted_inline = redact_text(inline)
    assert redacted_inline is not None

    assert basic_credential not in redacted_inline
    assert bearer_token not in redacted_inline
    assert "Authorization: [REDACTED]" in redacted_inline
    assert "dGVzdF91c2Vy" not in redacted_inline
    assert "Rlc3RfcGFzcw" not in redacted_inline

    structured = {
        "headers": {
            "Authorization": f"Basic {basic_credential}",
            "x-request-id": "req-123",
        },
        "error": json.dumps({"Authorization": f"Basic {basic_credential}"}),
    }
    redacted_structured = redact_secrets(structured)
    encoded = json.dumps(redacted_structured, sort_keys=True)

    assert basic_credential not in encoded
    assert redacted_structured["headers"]["Authorization"] == "[REDACTED]"
    assert redacted_structured["headers"]["x-request-id"] == "req-123"
    assert '"Authorization": "[REDACTED]"' in redacted_structured["error"]


def test_digest_authorization_headers_are_redacted_without_parameter_tail_leaks():
    digest_response = "digest_response_" + "raw_tail_secret"
    oauth_signature = "oauth_signature_" + "raw_tail_secret"
    inline = (
        f'upstream failed Authorization: Digest username="orvo", response="{digest_response}"; '
        f'retry with Authorization: OAuth oauth_consumer_key="orvo", oauth_signature="{oauth_signature}"'
    )

    redacted_inline = redact_text(inline)

    assert redacted_inline is not None
    assert digest_response not in redacted_inline
    assert oauth_signature not in redacted_inline
    assert "raw_tail_secret" not in redacted_inline
    assert redacted_inline.count("Authorization: [REDACTED]") == 2

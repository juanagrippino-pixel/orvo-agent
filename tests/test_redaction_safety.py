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



def test_cookie_headers_are_redacted_without_cookie_tail_leaks():
    session_cookie = "sess_" + "tail_12345"
    csrf_cookie = "csrf_" + "tail_67890"

    inline = (
        f"upstream failed Cookie: sessionid={session_cookie}; csrftoken={csrf_cookie} "
        "while syncing orders"
    )
    redacted_inline = redact_text(inline)
    assert redacted_inline is not None

    assert session_cookie not in redacted_inline
    assert csrf_cookie not in redacted_inline
    assert redacted_inline == "upstream failed Cookie: [REDACTED] while syncing orders"

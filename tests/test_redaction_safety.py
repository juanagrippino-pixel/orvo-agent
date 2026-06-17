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


def test_api_key_headers_are_redacted_without_header_tail_leaks():
    header_secret = "api_key_" + "header_tail_12345"
    compact_secret = "api_key_" + "compact_tail_67890"
    json_secret = "api_key_" + "json_tail_24680"

    inline = (
        f"upstream failed X-API-Key: {header_secret}; "
        f"retry with api-key={compact_secret} while syncing orders"
    )
    redacted_inline = redact_text(inline)
    assert redacted_inline is not None

    assert header_secret not in redacted_inline
    assert compact_secret not in redacted_inline
    assert "X-API-Key: [REDACTED]" in redacted_inline
    assert "api-key=[REDACTED]" in redacted_inline

    json_inline = f'connector payload {{"x-api-key": "{json_secret}"}}'
    redacted_json_inline = redact_text(json_inline)
    assert redacted_json_inline is not None
    assert json_secret not in redacted_json_inline
    assert '"x-api-key": "[REDACTED]"' in redacted_json_inline

    structured = {
        "headers": {
            "X-API-Key": header_secret,
            "x_api_key": compact_secret,
            "x-request-id": "req-123",
        },
        "error": json.dumps({"X-API-Key": header_secret}),
    }
    redacted_structured = redact_secrets(structured)
    encoded = json.dumps(redacted_structured, sort_keys=True)

    assert header_secret not in encoded
    assert compact_secret not in encoded
    assert redacted_structured["headers"]["X-API-Key"] == "[REDACTED]"
    assert redacted_structured["headers"]["x_api_key"] == "[REDACTED]"
    assert redacted_structured["headers"]["x-request-id"] == "req-123"
    assert '"X-API-Key": "[REDACTED]"' in redacted_structured["error"]

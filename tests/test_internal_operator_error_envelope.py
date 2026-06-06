from __future__ import annotations

from app.http.internal_brain.common import _internal_error
from server import app


def test_internal_error_redacts_secret_shaped_message_at_api_boundary():
    with app.test_request_context(
        "/internal/brain/businesses/artemea/cases",
        headers={"X-Request-ID": "req-error-redaction"},
    ):
        response, status_code = _internal_error(
            "artemea",
            "unsafe_error",
            "upstream failed with access_token=raw_internal_error_secret",
            status_code=502,
        )

    assert status_code == 502
    raw_body = response.get_data(as_text=True)
    assert "raw_internal_error_secret" not in raw_body
    body = response.get_json()
    assert body["ok"] is False
    assert body["request_id"] == "req-error-redaction"
    assert body["error"]["code"] == "unsafe_error"
    assert "[REDACTED" in body["error"]["message"]
    assert body["error"]["safe_to_show_owner"] is False
    assert body["redaction_applied"] is True

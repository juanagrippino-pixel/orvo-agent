from __future__ import annotations

from app.http.internal_brain.common import _internal_error, _internal_success
from server import app


def test_internal_success_redacts_secret_shaped_data_at_api_boundary():
    leaked_secret = "raw_" + "internal_success_secret"
    with app.test_request_context(
        "/internal/brain/businesses/artemea/cases",
        headers={"X-Request-ID": "req-success-redaction"},
    ):
        response = _internal_success(
            "artemea",
            {
                "case": {
                    "title": "safe title",
                    "metadata": {
                        "access_token": leaked_secret,
                        "provider_ref": f"https://provider.example/callback?code={leaked_secret}",
                    },
                    "notes": f"upstream returned Authorization: Basic {leaked_secret}",
                }
            },
        )

    raw_body = response.get_data(as_text=True)
    assert leaked_secret not in raw_body
    body = response.get_json()
    assert body["ok"] is True
    assert body["request_id"] == "req-success-redaction"
    assert body["data"]["case"]["metadata"]["access_token"] == "[REDACTED]"
    assert "code=%5BREDACTED%5D" in body["data"]["case"]["metadata"]["provider_ref"]
    assert body["data"]["case"]["notes"] == "upstream returned Authorization: [REDACTED]"
    assert body["redaction_applied"] is True


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


def test_internal_error_collapses_secret_shaped_error_code_at_api_boundary():
    leaked_secret = "raw_" + "internal_code_secret"
    unsafe_code = "invalid_limit access_token=" + leaked_secret
    with app.test_request_context(
        "/internal/brain/businesses/artemea/cases",
        headers={"X-Request-ID": "req-error-code-redaction"},
    ):
        response, status_code = _internal_error(
            "artemea",
            unsafe_code,
            "limit failed safely",
            status_code=400,
        )

    assert status_code == 400
    raw_body = response.get_data(as_text=True)
    assert leaked_secret not in raw_body
    body = response.get_json()
    assert body["ok"] is False
    assert body["request_id"] == "req-error-code-redaction"
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "limit failed safely"
    assert body["error"]["safe_to_show_owner"] is False
    assert body["redaction_applied"] is True


def test_internal_error_rejects_unstable_error_code_shapes_at_api_boundary():
    with app.test_request_context(
        "/internal/brain/businesses/artemea/cases",
        headers={"X-Request-ID": "req-error-code-shape"},
    ):
        response, status_code = _internal_error(
            "artemea",
            "Invalid Code With Spaces And Symbols!",
            "static message",
            status_code=500,
        )

    assert status_code == 500
    body = response.get_json()
    assert body["error"]["code"] == "internal_error"

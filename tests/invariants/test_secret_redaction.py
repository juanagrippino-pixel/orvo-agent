def test_redact_secrets_handles_bearer_headers_url_tokens_private_keys_and_nested_metadata():
    from app.brain.security.redaction import redact_secrets

    raw = {
        "status": "failed",
        "business_id": "artemea",
        "auth_header": "Bearer live_token_123",
        "callback": "https://api.example.test/orders?access_token=raw-token&safe=ok",
        "oauth_callback": "https://oauth.example.test/callback?code=oauth_callback_secret&state=safe-state",
        "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
        "nested": {
            "message": "refresh_token=refresh_secret and safe id case-123",
            "json_error": "request failed: {\"access_token\":\"secret_json_token\"}",
            "colon_error": "token: plain_colon_token",
            "oauth_error": "authorization_code=inline_oauth_secret",
            "quoted_oauth_error": "oauth_code: \"multi word oauth secret\"",
            "quoted_password": "request failed: {\"password\":\"two words secret\"}",
            "quoted_colon_password": "password: \"phrase secret value\"",
            "safe_status": "ok",
        },
    }

    redacted = redact_secrets(raw)
    rendered = str(redacted)

    assert redacted["status"] == "failed"
    assert redacted["business_id"] == "artemea"
    assert redacted["nested"]["safe_status"] == "ok"
    assert "live_token_123" not in rendered
    assert "raw-token" not in rendered
    assert "oauth_callback_secret" not in rendered
    assert "inline_oauth_secret" not in rendered
    assert "multi word oauth secret" not in rendered
    assert "refresh_secret" not in rendered
    assert "secret_json_token" not in rendered
    assert "plain_colon_token" not in rendered
    assert "two words secret" not in rendered
    assert "phrase secret value" not in rendered
    assert "abc" not in rendered
    assert "safe=ok" in rendered
    assert "state=safe-state" in rendered


def test_redact_text_removes_multi_token_basic_authorization_headers():
    from app.brain.security.redaction import redact_text

    text = "connector failed with Authorization: Basic dXNlcjpzdXBlcl9zZWNyZXQ= while syncing"

    redacted = redact_text(text)

    assert "Basic dXNlcjpzdXBlcl9zZWNyZXQ=" not in (redacted or "")
    assert "dXNlcjpzdXBlcl9zZWNyZXQ=" not in (redacted or "")
    assert redacted == "connector failed with Authorization: [REDACTED] while syncing"


def test_redact_text_redacts_bare_oauth_code_key_values_without_dropping_context():
    from app.brain.security.redaction import redact_text

    text = "oauth callback failed before code=raw_oauth_code after state=safe-state"

    redacted = redact_text(text)

    assert redacted == "oauth callback failed before code=[REDACTED] after state=safe-state"
    assert "raw_oauth_code" not in (redacted or "")
    assert "oauth callback failed before" in (redacted or "")
    assert "after state=safe-state" in (redacted or "")

from app.brain.runtime_env import check_runtime_env, RuntimeEnvCheck


def test_runtime_env_check_reports_missing_whatsapp_credentials_without_values():
    result = check_runtime_env(env={})

    assert isinstance(result, RuntimeEnvCheck)
    assert result.ready is False
    assert "WHATSAPP_PHONE_ID" in result.missing
    assert "WHATSAPP_TOKEN" in result.missing
    assert "WHATSAPP_TOKEN=" not in result.summary


def test_runtime_env_check_accepts_required_whatsapp_credentials():
    result = check_runtime_env(env={"WHATSAPP_PHONE_ID": "123", "WHATSAPP_TOKEN": "secret-token"})

    assert result.ready is True
    assert result.missing == []
    assert "secret-token" not in result.summary
    assert "configured" in result.summary


def test_runtime_env_check_can_validate_google_oauth_requirements():
    result = check_runtime_env(
        env={"WHATSAPP_PHONE_ID": "123", "WHATSAPP_TOKEN": "secret-token"},
        connectors=["google_sheets"],
    )

    assert result.ready is False
    assert "GOOGLE_CLIENT_SECRET_FILE" in result.missing
    assert "GOOGLE_OAUTH_TOKEN_FILE" in result.missing


def test_runtime_env_check_can_validate_tiendanube_requirements():
    result = check_runtime_env(
        env={"WHATSAPP_PHONE_ID": "123", "WHATSAPP_TOKEN": "secret-token"},
        connectors=["tiendanube"],
    )

    assert result.ready is False
    assert "TIENDANUBE_USER_ID" in result.missing
    assert "TIENDANUBE_ACCESS_TOKEN" in result.missing


def test_runtime_env_check_never_exposes_secret_values():
    result = check_runtime_env(
        env={
            "WHATSAPP_PHONE_ID": "123",
            "WHATSAPP_TOKEN": "wa-secret",
            "GOOGLE_CLIENT_SECRET_FILE": "/tmp/client.json",
            "GOOGLE_OAUTH_TOKEN_FILE": "/tmp/token.json",
            "TIENDANUBE_USER_ID": "999",
            "TIENDANUBE_ACCESS_TOKEN": "tn-secret",
        },
        connectors=["google_sheets", "tiendanube"],
    )

    assert result.ready is True
    assert "wa-secret" not in result.summary
    assert "tn-secret" not in result.summary
    assert "/tmp/client.json" not in result.summary
    assert "/tmp/token.json" not in result.summary


def test_runtime_env_check_accepts_twilio_whatsapp_credentials():
    result = check_runtime_env(
        env={
            "WHATSAPP_PROVIDER": "twilio",
            "TWILIO_ACCOUNT_SID": "AC123",
            "TWILIO_AUTH_TOKEN": "twilio-secret",
            "TWILIO_WHATSAPP_NUMBER": "whatsapp:+14155238886",
        }
    )

    assert result.ready is True
    assert result.missing == []
    assert "twilio-secret" not in result.summary

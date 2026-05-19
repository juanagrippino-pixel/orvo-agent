from pathlib import Path


def test_get_sheets_service_supports_user_oauth_token(monkeypatch, tmp_path):
    from app.brain.adapters import google_sheets

    client_secret = tmp_path / "client_secret.json"
    token = tmp_path / "token.json"
    client_secret.write_text(
        '{"installed":{"client_id":"client-id","client_secret":"client-secret","token_uri":"https://oauth2.googleapis.com/token"}}'
    )
    token.write_text(
        '{"token":"access-token","refresh_token":"refresh-token","scopes":["https://www.googleapis.com/auth/spreadsheets"]}'
    )
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET_FILE", str(client_secret))
    monkeypatch.setenv("GOOGLE_OAUTH_TOKEN_FILE", str(token))
    monkeypatch.delenv("GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE", raising=False)

    captured = {}

    class FakeCredentials:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    def fake_build(api, version, credentials):
        captured["api"] = api
        captured["version"] = version
        captured["credentials"] = credentials
        return "sheets-service"

    monkeypatch.setattr("google.oauth2.credentials.Credentials", FakeCredentials)
    monkeypatch.setattr("googleapiclient.discovery.build", fake_build)

    service = google_sheets.get_sheets_service()

    assert service == "sheets-service"
    assert captured["token"] == "access-token"
    assert captured["refresh_token"] == "refresh-token"
    assert captured["client_id"] == "client-id"
    assert captured["client_secret"] == "client-secret"
    assert captured["api"] == "sheets"
    assert captured["version"] == "v4"


def test_get_sheets_service_requires_credentials_when_none_configured(monkeypatch, tmp_path):
    import pytest
    from app.brain.adapters.google_sheets import get_sheets_service

    monkeypatch.delenv("GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET_FILE", str(tmp_path / "missing_client_secret.json"))
    monkeypatch.setenv("GOOGLE_OAUTH_TOKEN_FILE", str(tmp_path / "missing_token.json"))

    with pytest.raises(ValueError, match="Google Sheets credentials are required"):
        get_sheets_service(credentials_file=None)

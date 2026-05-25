"""TDD tests for WhatsApp delivery layer — no real network calls."""

from datetime import date
from unittest.mock import MagicMock, call
import pytest

from app.brain.delivery import (
    DeliveryResult,
    DeliveryTarget,
    WhatsAppDeliveryClient,
    build_report_delivery_payload,
    make_idempotency_key,
)


# ---------------------------------------------------------------------------
# DeliveryTarget
# ---------------------------------------------------------------------------


def test_delivery_target_stores_phone_and_business_id():
    target = DeliveryTarget(phone="+5491112345678", business_id="artemea")
    assert target.phone == "+5491112345678"
    assert target.business_id == "artemea"


def test_delivery_target_rejects_empty_phone():
    with pytest.raises(Exception):
        DeliveryTarget(phone="", business_id="artemea")


def test_delivery_target_rejects_empty_business_id():
    with pytest.raises(Exception):
        DeliveryTarget(phone="+5491112345678", business_id="")


# ---------------------------------------------------------------------------
# DeliveryResult
# ---------------------------------------------------------------------------


def test_delivery_result_success():
    result = DeliveryResult(success=True, message_id="wam_abc123", error=None)
    assert result.success is True
    assert result.message_id == "wam_abc123"
    assert result.error is None


def test_delivery_result_failure():
    result = DeliveryResult(success=False, message_id=None, error="rate limited")
    assert result.success is False
    assert result.error == "rate limited"


# ---------------------------------------------------------------------------
# make_idempotency_key
# ---------------------------------------------------------------------------


def test_idempotency_key_format():
    key = make_idempotency_key(
        business_id="artemea",
        report_date=date(2026, 5, 19),
        report_type="daily",
    )
    assert key == "artemea/2026-05-19/daily"


def test_idempotency_key_different_dates_differ():
    k1 = make_idempotency_key("biz", date(2026, 5, 19), "daily")
    k2 = make_idempotency_key("biz", date(2026, 5, 20), "daily")
    assert k1 != k2


def test_idempotency_key_different_types_differ():
    k1 = make_idempotency_key("biz", date(2026, 5, 19), "daily")
    k2 = make_idempotency_key("biz", date(2026, 5, 19), "weekly")
    assert k1 != k2


# ---------------------------------------------------------------------------
# build_report_delivery_payload
# ---------------------------------------------------------------------------


def test_build_payload_wraps_text_as_whatsapp_text_message():
    target = DeliveryTarget(phone="+5491112345678", business_id="artemea")
    payload = build_report_delivery_payload(
        report_text="Hola, este es el reporte.", target=target
    )
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "+5491112345678"
    assert payload["type"] == "text"
    assert payload["text"]["body"] == "Hola, este es el reporte."


def test_build_payload_does_not_preview_links_by_default():
    target = DeliveryTarget(phone="+5491112345678", business_id="artemea")
    payload = build_report_delivery_payload("texto", target=target)
    assert payload["text"].get("preview_url") is False


def test_build_payload_rejects_empty_report_text():
    target = DeliveryTarget(phone="+5491112345678", business_id="artemea")
    with pytest.raises(ValueError, match="report_text"):
        build_report_delivery_payload("", target=target)


# ---------------------------------------------------------------------------
# WhatsAppDeliveryClient — injected http client (no network)
# ---------------------------------------------------------------------------


def _mock_http(status_code=200, json_body=None):
    """Return a mock requests-like session with a configurable response."""
    if json_body is None:
        json_body = {"messages": [{"id": "wam_test_001"}]}
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body
    session = MagicMock()
    session.post.return_value = response
    return session


def test_send_text_returns_success_on_200():
    session = _mock_http(200, {"messages": [{"id": "wam_xyz"}]})
    client = WhatsAppDeliveryClient(
        phone_id="123456789",
        token="test_token",
        http_client=session,
    )
    result = client.send_text(phone="+5491112345678", text="Hola!")
    assert result.success is True
    assert result.message_id == "wam_xyz"
    assert result.error is None


def test_send_text_posts_to_correct_whatsapp_api_url():
    session = _mock_http()
    client = WhatsAppDeliveryClient(
        phone_id="PHONE123",
        token="TOKEN",
        http_client=session,
    )
    client.send_text(phone="+5491112345678", text="Test")
    posted_url = session.post.call_args[0][0]
    assert "PHONE123" in posted_url
    assert "messages" in posted_url
    assert "graph.facebook.com" in posted_url


def test_send_text_sends_bearer_auth_header():
    session = _mock_http()
    client = WhatsAppDeliveryClient(
        phone_id="PHONE123",
        token="SECRET_TOKEN",
        http_client=session,
    )
    client.send_text(phone="+5491112345678", text="Test")
    kwargs = session.post.call_args[1]
    headers = kwargs.get("headers", {})
    assert headers.get("Authorization") == "Bearer SECRET_TOKEN"


def test_send_text_returns_failure_on_4xx():
    session = _mock_http(400, {"error": {"message": "Invalid phone"}})
    client = WhatsAppDeliveryClient(
        phone_id="P",
        token="T",
        http_client=session,
    )
    result = client.send_text(phone="+bad", text="Hi")
    assert result.success is False
    assert result.message_id is None
    assert "400" in result.error or "Invalid" in result.error


def test_send_text_returns_failure_on_5xx():
    session = _mock_http(500, {"error": {"message": "Server error"}})
    client = WhatsAppDeliveryClient(phone_id="P", token="T", http_client=session)
    result = client.send_text(phone="+5491112345678", text="Hi")
    assert result.success is False
    assert result.error is not None


def test_send_text_handles_network_exception():
    session = MagicMock()
    session.post.side_effect = ConnectionError("Network unreachable")
    client = WhatsAppDeliveryClient(phone_id="P", token="T", http_client=session)
    result = client.send_text(phone="+5491112345678", text="Hi")
    assert result.success is False
    assert "Network unreachable" in result.error


def test_send_text_posts_correct_json_body():
    session = _mock_http()
    client = WhatsAppDeliveryClient(phone_id="P", token="T", http_client=session)
    client.send_text(phone="+5491112345678", text="Reporte listo")
    kwargs = session.post.call_args[1]
    body = kwargs.get("json", {})
    assert body["messaging_product"] == "whatsapp"
    assert body["to"] == "+5491112345678"
    assert body["type"] == "text"
    assert body["text"]["body"] == "Reporte listo"


def test_client_from_env_uses_env_vars(monkeypatch):
    """Runtime constructor reads from environment variables."""
    monkeypatch.delenv("WHATSAPP_PROVIDER", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_NUMBER", raising=False)
    monkeypatch.setenv("WHATSAPP_PHONE_ID", "ENV_PHONE")
    monkeypatch.setenv("WHATSAPP_TOKEN", "ENV_TOKEN")
    client = WhatsAppDeliveryClient.from_env()
    assert client._phone_id == "ENV_PHONE"
    assert client._token == "ENV_TOKEN"


def test_client_from_env_raises_if_missing(monkeypatch):
    monkeypatch.delenv("WHATSAPP_PROVIDER", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_NUMBER", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_ID", raising=False)
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    with pytest.raises(EnvironmentError):
        WhatsAppDeliveryClient.from_env()


def test_client_from_env_supports_twilio_provider(monkeypatch):
    monkeypatch.setenv("WHATSAPP_PROVIDER", "twilio")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-secret")
    monkeypatch.setenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

    client = WhatsAppDeliveryClient.from_env()

    assert client._provider == "twilio"
    assert client._twilio_account_sid == "AC123"
    assert client._twilio_whatsapp_number == "whatsapp:+14155238886"


def test_client_from_env_twilio_raises_if_missing(monkeypatch):
    monkeypatch.setenv("WHATSAPP_PROVIDER", "twilio")
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_NUMBER", raising=False)

    with pytest.raises(EnvironmentError):
        WhatsAppDeliveryClient.from_env()


def test_send_text_uses_twilio_whatsapp_api_when_provider_is_twilio():
    session = _mock_http(201, {"sid": "SM123"})
    client = WhatsAppDeliveryClient(
        phone_id="unused",
        token="unused",
        http_client=session,
        provider="twilio",
        twilio_account_sid="AC123",
        twilio_auth_token="twilio-secret",
        twilio_whatsapp_number="whatsapp:+14155238886",
    )

    result = client.send_text(phone="+5491112345678", text="Hola Twilio")

    assert result.success is True
    assert result.message_id == "SM123"
    posted_url = session.post.call_args[0][0]
    assert posted_url.endswith("/Accounts/AC123/Messages.json")
    kwargs = session.post.call_args[1]
    assert kwargs["data"]["From"] == "whatsapp:+14155238886"
    assert kwargs["data"]["To"] == "whatsapp:+5491112345678"
    assert kwargs["data"]["Body"] == "Hola Twilio"
    assert kwargs["auth"] == ("AC123", "twilio-secret")


def test_send_text_twilio_returns_failure_on_error_response():
    session = _mock_http(400, {"message": "The 'To' number is not a valid WhatsApp-capable number"})
    client = WhatsAppDeliveryClient(
        phone_id="unused",
        token="unused",
        http_client=session,
        provider="twilio",
        twilio_account_sid="AC123",
        twilio_auth_token="twilio-secret",
        twilio_whatsapp_number="whatsapp:+14155238886",
    )

    result = client.send_text(phone="+5491112345678", text="Hola Twilio")

    assert result.success is False
    assert result.message_id is None
    assert "400" in result.error


# ---------------------------------------------------------------------------
# Meta Cloud API contract — default provider, env aliases, status codes
# ---------------------------------------------------------------------------


def test_client_from_env_defaults_to_meta_cloud(monkeypatch):
    """Unset WHATSAPP_PROVIDER must default to Meta Cloud (Orvo's own number)."""
    monkeypatch.delenv("WHATSAPP_PROVIDER", raising=False)
    monkeypatch.setenv("WHATSAPP_PHONE_ID", "P")
    monkeypatch.setenv("WHATSAPP_TOKEN", "T")

    client = WhatsAppDeliveryClient.from_env()

    assert client._provider == "meta_cloud"


def test_client_from_env_accepts_meta_native_aliases(monkeypatch):
    """Meta-native env names act as aliases for the existing var names."""
    monkeypatch.delenv("WHATSAPP_PROVIDER", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_ID", raising=False)
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "META_PHONE")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "META_TOKEN")

    client = WhatsAppDeliveryClient.from_env()

    assert client._phone_id == "META_PHONE"
    assert client._token == "META_TOKEN"


def test_client_from_env_existing_names_take_precedence_over_aliases(monkeypatch):
    """If both existing and Meta-native env names are set, existing wins."""
    monkeypatch.delenv("WHATSAPP_PROVIDER", raising=False)
    monkeypatch.setenv("WHATSAPP_PHONE_ID", "EXISTING_PHONE")
    monkeypatch.setenv("WHATSAPP_TOKEN", "EXISTING_TOKEN")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "META_PHONE")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "META_TOKEN")

    client = WhatsAppDeliveryClient.from_env()

    assert client._phone_id == "EXISTING_PHONE"
    assert client._token == "EXISTING_TOKEN"


def test_client_from_env_rejects_unsupported_provider(monkeypatch):
    """An unsupported WHATSAPP_PROVIDER must fail fast (not silently use Meta)."""
    monkeypatch.setenv("WHATSAPP_PROVIDER", "gupshup")
    monkeypatch.setenv("WHATSAPP_PHONE_ID", "P")
    monkeypatch.setenv("WHATSAPP_TOKEN", "T")

    with pytest.raises(ValueError) as excinfo:
        WhatsAppDeliveryClient.from_env()

    message = str(excinfo.value)
    assert "WHATSAPP_PROVIDER" in message
    assert "gupshup" in message
    # Supported providers should be enumerated for the operator.
    assert "meta_cloud" in message
    assert "twilio" in message


def test_send_text_meta_returns_success_on_201_with_message_id():
    """Meta Cloud sometimes responds 201 Created — also a success when id present."""
    session = _mock_http(201, {"messages": [{"id": "wam_201"}]})
    client = WhatsAppDeliveryClient(phone_id="P", token="T", http_client=session)

    result = client.send_text(phone="+5491112345678", text="Hola")

    assert result.success is True
    assert result.message_id == "wam_201"
    assert result.error is None


def test_send_text_meta_payload_disables_link_preview():
    """Meta send-text body must include text.preview_url = False explicitly."""
    session = _mock_http()
    client = WhatsAppDeliveryClient(phone_id="P", token="T", http_client=session)

    client.send_text(phone="+5491112345678", text="Reporte")

    body = session.post.call_args[1]["json"]
    assert body["text"]["preview_url"] is False


# ---------------------------------------------------------------------------
# Error redaction — bearer tokens / auth tokens must never leak
# ---------------------------------------------------------------------------


def test_send_text_meta_redacts_bearer_token_in_network_exception():
    session = MagicMock()
    session.post.side_effect = RuntimeError(
        "Connection failed; sent header Authorization: Bearer SECRET_TOKEN_XYZ"
    )
    client = WhatsAppDeliveryClient(
        phone_id="P", token="SECRET_TOKEN_XYZ", http_client=session
    )

    result = client.send_text(phone="+5491112345678", text="Hi")

    assert result.success is False
    assert "SECRET_TOKEN_XYZ" not in (result.error or "")
    assert "[REDACTED]" in (result.error or "")


def test_send_text_meta_redacts_access_token_in_error_body():
    session = _mock_http(
        400,
        {"error": {"message": "Invalid access_token=SECRET_TOKEN_XYZ"}},
    )
    client = WhatsAppDeliveryClient(
        phone_id="P", token="SECRET_TOKEN_XYZ", http_client=session
    )

    result = client.send_text(phone="+5491112345678", text="Hi")

    assert result.success is False
    assert "SECRET_TOKEN_XYZ" not in (result.error or "")
    assert "[REDACTED]" in (result.error or "")


def test_send_text_twilio_redacts_basic_auth_header_in_network_exception():
    """Twilio uses HTTP Basic — a leaked Authorization: Basic header must be redacted."""
    session = MagicMock()
    session.post.side_effect = RuntimeError(
        "Request failed; sent Authorization: Basic QUMxMjM6VFdJTElPX1JBV19TRUNSRVQ="
    )
    client = WhatsAppDeliveryClient(
        phone_id="unused",
        token="unused",
        http_client=session,
        provider="twilio",
        twilio_account_sid="AC123",
        twilio_auth_token="TWILIO_RAW_SECRET",
        twilio_whatsapp_number="whatsapp:+14155238886",
    )

    result = client.send_text(phone="+5491112345678", text="Hi")

    assert result.success is False
    assert "QUMxMjM6VFdJTElPX1JBV19TRUNSRVQ=" not in (result.error or "")
    assert "[REDACTED]" in (result.error or "")

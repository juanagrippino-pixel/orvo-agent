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
    monkeypatch.setenv("WHATSAPP_PHONE_ID", "ENV_PHONE")
    monkeypatch.setenv("WHATSAPP_TOKEN", "ENV_TOKEN")
    client = WhatsAppDeliveryClient.from_env()
    assert client._phone_id == "ENV_PHONE"
    assert client._token == "ENV_TOKEN"


def test_client_from_env_raises_if_missing(monkeypatch):
    monkeypatch.delenv("WHATSAPP_PHONE_ID", raising=False)
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    with pytest.raises(EnvironmentError):
        WhatsAppDeliveryClient.from_env()

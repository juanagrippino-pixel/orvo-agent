"""Tests for the WhatsApp delivery status webhook integration and internal read endpoint."""

from __future__ import annotations

import json
import sqlite3

import pytest

from app.brain.storage import init_schema


AUTH = {"Authorization": "Bearer test-internal-token", "X-Orvo-Operator": "operator:juan", "X-Request-ID": "req-test"}


def _client(monkeypatch, tmp_path):
    db_path = tmp_path / "delivery.sqlite3"
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
    from server import app

    return app.test_client(), db_path


def _status_payload(*, message_id="wamid.STATUS1", status="delivered", timestamp="1748000000"):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "1234567890"},
                            "statuses": [
                                {
                                    "id": message_id,
                                    "status": status,
                                    "timestamp": timestamp,
                                    "recipient_id": "5491150380097",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _read_status_rows(db_path):
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    rows = conn.execute(
        "SELECT message_id, status, recipient_id, provider FROM whatsapp_delivery_status_events"
    ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


def test_webhook_persists_status_only_payload(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    response = client.post("/webhook", json=_status_payload())
    assert response.status_code == 200
    rows = _read_status_rows(db_path)
    assert len(rows) == 1
    message_id, status, recipient_id, provider = rows[0]
    assert message_id == "wamid.STATUS1"
    assert status == "delivered"
    assert recipient_id == "5491150380097"
    assert provider == "meta_cloud"


def test_webhook_deduplicates_repeated_status_delivery(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    payload = _status_payload()
    assert client.post("/webhook", json=payload).status_code == 200
    assert client.post("/webhook", json=payload).status_code == 200
    rows = _read_status_rows(db_path)
    assert len(rows) == 1


def test_webhook_persists_multiple_statuses_for_same_message(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    assert client.post(
        "/webhook", json=_status_payload(message_id="wamid.MULTI", status="sent", timestamp="1748001000")
    ).status_code == 200
    assert client.post(
        "/webhook",
        json=_status_payload(message_id="wamid.MULTI", status="delivered", timestamp="1748001100"),
    ).status_code == 200
    rows = _read_status_rows(db_path)
    assert sorted(row[1] for row in rows) == ["delivered", "sent"]


def test_webhook_handles_malformed_status_payload_without_500(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    malformed = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"statuses": "not-a-list"}}]}],
    }
    response = client.post("/webhook", json=malformed)
    assert response.status_code == 200
    assert _read_status_rows(db_path) == []


def test_webhook_status_only_payload_does_not_trigger_inbound_message_buffer(monkeypatch, tmp_path):
    """Status-only payloads must not be misinterpreted as inbound text messages."""
    client, db_path = _client(monkeypatch, tmp_path)
    called: list[str] = []

    import server

    monkeypatch.setattr(server.threading, "Timer", lambda *a, **k: called.append("timer-created") or (_ for _ in ()).throw(AssertionError("no timer for status-only payload")))

    response = client.post("/webhook", json=_status_payload())
    assert response.status_code == 200
    assert called == []


# ---------------------------------------------------------------------------
# Internal endpoint
# ---------------------------------------------------------------------------


def test_internal_delivery_statuses_requires_auth(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    response = client.get("/internal/brain/whatsapp/delivery-statuses")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthorized"


def test_internal_delivery_statuses_returns_recent_events(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    assert client.post("/webhook", json=_status_payload(message_id="wamid.A", status="sent", timestamp="1748002000")).status_code == 200
    assert client.post("/webhook", json=_status_payload(message_id="wamid.A", status="delivered", timestamp="1748002100")).status_code == 200
    assert client.post("/webhook", json=_status_payload(message_id="wamid.B", status="read", timestamp="1748002200")).status_code == 200

    response = client.get("/internal/brain/whatsapp/delivery-statuses", headers=AUTH)
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["request_id"] == "req-test"
    assert body["redaction_applied"] is True
    events = body["data"]["events"]
    assert len(events) == 3
    assert all(e["provider"] == "meta_cloud" for e in events)
    assert {e["message_id"] for e in events} == {"wamid.A", "wamid.B"}


def test_internal_delivery_statuses_allows_viewer_read_role(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    assert client.post("/webhook", json=_status_payload(message_id="wamid.VIEW", status="delivered")).status_code == 200

    response = client.get(
        "/internal/brain/whatsapp/delivery-statuses",
        headers={**AUTH, "X-Orvo-Role": "viewer"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["business_id"] == "whatsapp"
    assert body["data"]["events"][0]["message_id"] == "wamid.VIEW"


def test_internal_delivery_statuses_denies_unknown_role_and_audits_redacted(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    raw_role_secret = "raw_delivery_role_secret"

    response = client.get(
        "/internal/brain/whatsapp/delivery-statuses?limit=not-an-int",
        headers={
            **AUTH,
            "X-Orvo-Role": f"access_token={raw_role_secret}",
            "X-Request-ID": "req-delivery-status-rbac-denied",
        },
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"
    assert raw_role_secret not in response.get_data(as_text=True)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT business_id, actor_ref, event_type, target_type, target_id, request_id, data
        FROM operator_audit_events
        ORDER BY created_at ASC
        """
    ).fetchall()
    conn.close()

    assert len(rows) == 1
    business_id, actor_ref, event_type, target_type, target_id, request_id, raw_data = rows[0]
    assert business_id == "whatsapp"
    assert actor_ref == "operator:juan"
    assert event_type == "internal_operator_authorization_denied"
    assert target_type == "internal_operator_api"
    assert target_id == "/internal/brain/whatsapp/delivery-statuses"
    assert request_id == "req-delivery-status-rbac-denied"
    assert raw_role_secret not in raw_data
    assert json.loads(raw_data) == {
        "method": "GET",
        "permission": "role:known",
        "reason": "unknown_operator_role",
        "role": "access_token=[REDACTED]",
        "status": "denied",
        "status_code": 403,
    }


def test_internal_delivery_statuses_redacts_failed_error_metadata(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    failure = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "statuses": [
                                {
                                    "id": "wamid.FAIL",
                                    "status": "failed",
                                    "timestamp": "1748003000",
                                    "recipient_id": "5491150380097",
                                    "errors": [
                                        {
                                            "code": 131000,
                                            "title": "Authorization: Bearer raw_endpoint_secret rejected",
                                            "error_data": {
                                                "access_token": "raw_endpoint_secret",
                                                "details": "details access_token=raw_endpoint_secret",
                                            },
                                        }
                                    ],
                                }
                            ]
                        },
                    }
                ],
            }
        ],
    }
    assert client.post("/webhook", json=failure).status_code == 200

    response = client.get("/internal/brain/whatsapp/delivery-statuses", headers=AUTH)
    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_endpoint_secret" not in raw_body
    body = response.get_json()
    events = body["data"]["events"]
    assert any(e["status"] == "failed" for e in events)


def test_webhook_persists_all_events_from_batched_multi_entry_payload(monkeypatch, tmp_path):
    """End-to-end regression: a Meta webhook delivery that batches lifecycle
    transitions across multiple ``entry[]`` and ``changes[]`` items must
    persist every status event. A future refactor of
    ``_persist_delivery_status_events`` that took ``entry[0].changes[0]`` —
    mirroring the inbound message branch — would pass parser unit tests but
    silently drop dispatch observability for batched deliveries.
    """
    client, db_path = _client(monkeypatch, tmp_path)
    batched = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {"id": "wamid.A", "status": "sent", "timestamp": "1748100000", "recipient_id": "5491150380097"},
                                {"id": "wamid.A", "status": "delivered", "timestamp": "1748100005", "recipient_id": "5491150380097"},
                                {"id": "wamid.A", "status": "read", "timestamp": "1748100010", "recipient_id": "5491150380097"},
                            ],
                        },
                    },
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {"id": "wamid.B", "status": "delivered", "timestamp": "1748100020", "recipient_id": "5491150380097"},
                            ],
                        },
                    },
                ],
            },
            {
                "id": "WABA-2",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {"id": "wamid.C", "status": "failed", "timestamp": "1748100030", "recipient_id": "5491150380097"},
                            ],
                        },
                    }
                ],
            },
        ],
    }
    assert client.post("/webhook", json=batched).status_code == 200
    rows = _read_status_rows(db_path)
    assert len(rows) == 5
    pairs = {(message_id, status) for message_id, status, _recipient, _provider in rows}
    assert pairs == {
        ("wamid.A", "sent"),
        ("wamid.A", "delivered"),
        ("wamid.A", "read"),
        ("wamid.B", "delivered"),
        ("wamid.C", "failed"),
    }


def test_webhook_persists_status_when_template_update_precedes_messages_change(monkeypatch, tmp_path):
    """End-to-end regression: when a non-``messages`` change (e.g. a
    ``message_template_status_update``) sits at ``changes[0]`` and a real
    ``messages`` change with ``statuses[]`` sits at ``changes[1]``, the webhook
    must still persist the status event without 500 or silent loss.
    """
    client, db_path = _client(monkeypatch, tmp_path)
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "message_template_status_update",
                        "value": {
                            "event": "APPROVED",
                            "message_template_name": "daily_report",
                        },
                    },
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {
                                    "id": "wamid.MIX",
                                    "status": "delivered",
                                    "timestamp": "1748100100",
                                    "recipient_id": "5491150380097",
                                }
                            ],
                        },
                    },
                ],
            }
        ],
    }
    response = client.post("/webhook", json=payload)
    assert response.status_code == 200
    rows = _read_status_rows(db_path)
    assert len(rows) == 1
    message_id, status, recipient_id, provider = rows[0]
    assert message_id == "wamid.MIX"
    assert status == "delivered"
    assert recipient_id == "5491150380097"
    assert provider == "meta_cloud"


def test_webhook_buffers_inbound_text_when_status_change_precedes_messages_change(monkeypatch, tmp_path):
    """Regression: Meta batches multiple ``changes[]`` in one webhook delivery.
    When ``changes[0]`` carries an outbound delivery ``statuses[]`` ack and
    ``changes[1]`` carries the inbound text reply, the legacy
    ``data["entry"][0]["changes"][0]["value"]`` shortcut silently drops the
    inbound message — no timer is scheduled, no buffer is populated, no error
    is logged. The webhook must walk every change to find the inbound
    ``messages[]`` array.
    """
    client, _db_path = _client(monkeypatch, tmp_path)

    import server

    scheduled: list[tuple] = []

    class _FakeTimer:
        def __init__(self, interval, function, args=None, kwargs=None):
            scheduled.append((interval, function, tuple(args or ())))

        def start(self) -> None:
            pass

        def cancel(self) -> None:
            pass

    monkeypatch.setattr(server.threading, "Timer", _FakeTimer)

    mixed = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {
                                    "id": "wamid.OUTBOUND",
                                    "status": "delivered",
                                    "timestamp": "1748200000",
                                    "recipient_id": "5491150380097",
                                }
                            ],
                        },
                    },
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": "5491150380097",
                                    "id": "wamid.INBOUND",
                                    "type": "text",
                                    "text": {"body": "hola, quiero info"},
                                }
                            ],
                        },
                    },
                ],
            }
        ],
    }

    response = client.post("/webhook", json=mixed)
    assert response.status_code == 200
    assert len(scheduled) == 1, "expected exactly one buffered-process timer for the inbound reply"
    _interval, _function, args = scheduled[0]
    assert args == ("5491150380097",)
    assert server._buffers.get("5491150380097") == ["hola, quiero info"]
    # Cleanup module-global state so we don't leak into other tests.
    server._buffers.pop("5491150380097", None)
    server._timers.pop("5491150380097", None)


def test_webhook_buffers_inbound_text_when_inbound_lives_in_second_entry(monkeypatch, tmp_path):
    """Regression: Meta can batch separate WABAs in ``entry[]``. When the
    inbound reply lives at ``entry[1].changes[0]``, the legacy
    ``data["entry"][0]"]`` shortcut silently drops it.
    """
    client, _db_path = _client(monkeypatch, tmp_path)

    import server

    scheduled: list[tuple] = []

    class _FakeTimer:
        def __init__(self, interval, function, args=None, kwargs=None):
            scheduled.append((interval, function, tuple(args or ())))

        def start(self) -> None:
            pass

        def cancel(self) -> None:
            pass

    monkeypatch.setattr(server.threading, "Timer", _FakeTimer)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {
                                    "id": "wamid.OUT",
                                    "status": "read",
                                    "timestamp": "1748200500",
                                    "recipient_id": "5491150380098",
                                }
                            ],
                        },
                    }
                ],
            },
            {
                "id": "WABA-2",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": "5491150380099",
                                    "id": "wamid.INBOUND2",
                                    "type": "text",
                                    "text": {"body": "necesito ayuda"},
                                }
                            ],
                        },
                    }
                ],
            },
        ],
    }

    response = client.post("/webhook", json=payload)
    assert response.status_code == 200
    assert len(scheduled) == 1
    _interval, _function, args = scheduled[0]
    assert args == ("5491150380099",)
    assert server._buffers.get("5491150380099") == ["necesito ayuda"]
    server._buffers.pop("5491150380099", None)
    server._timers.pop("5491150380099", None)


def test_internal_delivery_statuses_respects_limit_bounds(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    for i in range(6):
        assert client.post(
            "/webhook",
            json=_status_payload(message_id=f"wamid.X{i}", status="delivered", timestamp=str(1748000000 + i)),
        ).status_code == 200

    response = client.get("/internal/brain/whatsapp/delivery-statuses?limit=3", headers=AUTH)
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["data"]["events"]) == 3

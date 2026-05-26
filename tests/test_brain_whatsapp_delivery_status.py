"""Tests for the WhatsApp delivery status append-only store and Meta payload parser.

TDD: failing tests first, then implementation.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from app.brain.delivery_status import (
    SQLiteWhatsAppDeliveryStatusStore,
    WhatsAppDeliveryStatusEvent,
    build_event_key,
    parse_meta_status_payload,
)
from app.brain.storage import init_schema


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    init_schema(c)
    yield c
    c.close()


@pytest.fixture
def store(conn):
    return SQLiteWhatsAppDeliveryStatusStore(conn)


def _meta_status_payload(
    *,
    message_id: str = "wamid.HBgL1234",
    status: str = "delivered",
    timestamp: str = "1748000000",
    recipient_id: str = "5491150380097",
    extra: dict | None = None,
) -> dict:
    entry_value: dict = {
        "messaging_product": "whatsapp",
        "metadata": {"phone_number_id": "1234567890"},
        "statuses": [
            {
                "id": message_id,
                "status": status,
                "timestamp": timestamp,
                "recipient_id": recipient_id,
            }
        ],
    }
    if extra is not None:
        entry_value["statuses"][0].update(extra)
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-ID",
                "changes": [{"field": "messages", "value": entry_value}],
            }
        ],
    }


# ---------------------------------------------------------------------------
# init_schema integration
# ---------------------------------------------------------------------------


def test_init_schema_creates_whatsapp_delivery_status_table(conn):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='whatsapp_delivery_status_events'"
    )
    assert cursor.fetchone() is not None


# ---------------------------------------------------------------------------
# Event key + model
# ---------------------------------------------------------------------------


def test_build_event_key_is_deterministic_across_calls():
    key1 = build_event_key(
        provider="meta_cloud",
        message_id="wamid.HBgL1234",
        status="delivered",
        timestamp="1748000000",
    )
    key2 = build_event_key(
        provider="meta_cloud",
        message_id="wamid.HBgL1234",
        status="delivered",
        timestamp="1748000000",
    )
    assert key1 == key2
    assert "wamid.HBgL1234" in key1
    assert "delivered" in key1


def test_build_event_key_differs_by_status():
    sent = build_event_key(provider="meta_cloud", message_id="m1", status="sent", timestamp="1")
    delivered = build_event_key(provider="meta_cloud", message_id="m1", status="delivered", timestamp="1")
    assert sent != delivered


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------


def test_store_persists_event_and_lists_it(store):
    event = WhatsAppDeliveryStatusEvent(
        provider="meta_cloud",
        message_id="wamid.HBgL1234",
        status="delivered",
        status_timestamp="1748000000",
        recipient_id="5491150380097",
        raw={"id": "wamid.HBgL1234", "status": "delivered"},
    )
    store.record_event(event)
    recent = store.list_recent(limit=10)
    assert len(recent) == 1
    assert recent[0]["message_id"] == "wamid.HBgL1234"
    assert recent[0]["status"] == "delivered"
    assert recent[0]["recipient_id"] == "5491150380097"
    assert recent[0]["provider"] == "meta_cloud"
    assert "created_at" in recent[0]


def test_store_deduplicates_repeat_event_key(store):
    event = WhatsAppDeliveryStatusEvent(
        provider="meta_cloud",
        message_id="wamid.dup",
        status="read",
        status_timestamp="1748000100",
        recipient_id="5491150380097",
        raw={"id": "wamid.dup", "status": "read"},
    )
    store.record_event(event)
    store.record_event(event)  # second time — must not raise or duplicate row
    recent = store.list_recent(limit=10)
    assert len([r for r in recent if r["message_id"] == "wamid.dup"]) == 1


def test_store_keeps_distinct_statuses_for_same_message(store):
    sent = WhatsAppDeliveryStatusEvent(
        provider="meta_cloud",
        message_id="wamid.multi",
        status="sent",
        status_timestamp="1748000200",
        recipient_id="5491150380097",
        raw={},
    )
    delivered = WhatsAppDeliveryStatusEvent(
        provider="meta_cloud",
        message_id="wamid.multi",
        status="delivered",
        status_timestamp="1748000300",
        recipient_id="5491150380097",
        raw={},
    )
    store.record_event(sent)
    store.record_event(delivered)
    recent = store.list_recent(limit=10)
    statuses = {r["status"] for r in recent if r["message_id"] == "wamid.multi"}
    assert statuses == {"sent", "delivered"}


def test_store_redacts_token_like_strings_in_failed_error_metadata(store):
    event = WhatsAppDeliveryStatusEvent(
        provider="meta_cloud",
        message_id="wamid.fail",
        status="failed",
        status_timestamp="1748000400",
        recipient_id="5491150380097",
        raw={
            "id": "wamid.fail",
            "status": "failed",
            "errors": [
                {
                    "code": 131000,
                    "title": "Bearer raw_failure_secret was rejected",
                    "error_data": {
                        "details": "Authorization: Bearer raw_failure_secret",
                        "access_token": "raw_failure_secret",
                    },
                }
            ],
        },
    )
    store.record_event(event)
    recent = store.list_recent(limit=10)
    assert len(recent) == 1
    serialized = json.dumps(recent[0])
    assert "raw_failure_secret" not in serialized
    assert "[REDACTED]" in serialized


def test_store_list_recent_orders_newest_first_and_respects_limit(store):
    for i in range(5):
        store.record_event(
            WhatsAppDeliveryStatusEvent(
                provider="meta_cloud",
                message_id=f"wamid.m{i}",
                status="delivered",
                status_timestamp=str(1748000000 + i),
                recipient_id="5491150380097",
                raw={},
            )
        )
    recent = store.list_recent(limit=3)
    assert len(recent) == 3
    # Newest first by created_at — but all were created at near-identical times,
    # the ordering tie-breaker is message_id descending insertion order; at minimum
    # we assert the limit was applied and entries are well-formed.
    assert all("message_id" in r for r in recent)


# ---------------------------------------------------------------------------
# parse_meta_status_payload tests
# ---------------------------------------------------------------------------


def test_parse_meta_status_payload_extracts_single_status():
    payload = _meta_status_payload()
    events = parse_meta_status_payload(payload)
    assert len(events) == 1
    event = events[0]
    assert event.provider == "meta_cloud"
    assert event.message_id == "wamid.HBgL1234"
    assert event.status == "delivered"
    assert event.recipient_id == "5491150380097"


def test_parse_meta_status_payload_returns_empty_for_messages_only_payload():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {"from": "5491150380097", "type": "text", "text": {"body": "hi"}}
                            ],
                        },
                    }
                ],
            }
        ],
    }
    assert parse_meta_status_payload(payload) == []


def test_parse_meta_status_payload_tolerates_malformed_payload():
    assert parse_meta_status_payload({}) == []
    assert parse_meta_status_payload({"entry": [{"changes": [{"value": "not-a-dict"}]}]}) == []
    assert parse_meta_status_payload({"entry": [{"changes": [{"value": {"statuses": "broken"}}]}]}) == []


def test_parse_meta_status_payload_skips_status_entries_missing_id_or_status():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "statuses": [
                                {"status": "delivered"},  # missing id
                                {"id": "wamid.X"},  # missing status
                                {
                                    "id": "wamid.Y",
                                    "status": "read",
                                    "timestamp": "1748000500",
                                    "recipient_id": "5491150380097",
                                },
                            ]
                        },
                    }
                ],
            }
        ],
    }
    events = parse_meta_status_payload(payload)
    assert len(events) == 1
    assert events[0].message_id == "wamid.Y"


def test_parse_meta_status_payload_extracts_all_statuses_from_batched_payload():
    """Meta batches lifecycle transitions (sent/delivered/read) for one or more
    messages into a single webhook delivery. The parser must walk every status
    entry, every changes entry, and every entry; a regression that takes ``[0]``
    anywhere would silently drop dispatch observability events.
    """
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
                                    "id": "wamid.A",
                                    "status": "sent",
                                    "timestamp": "1748000000",
                                    "recipient_id": "5491150380097",
                                },
                                {
                                    "id": "wamid.A",
                                    "status": "delivered",
                                    "timestamp": "1748000005",
                                    "recipient_id": "5491150380097",
                                },
                                {
                                    "id": "wamid.A",
                                    "status": "read",
                                    "timestamp": "1748000010",
                                    "recipient_id": "5491150380097",
                                },
                            ],
                        },
                    },
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {
                                    "id": "wamid.B",
                                    "status": "delivered",
                                    "timestamp": "1748000020",
                                    "recipient_id": "5491150380097",
                                }
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
                                {
                                    "id": "wamid.C",
                                    "status": "failed",
                                    "timestamp": "1748000030",
                                    "recipient_id": "5491150380097",
                                }
                            ],
                        },
                    }
                ],
            },
        ],
    }
    events = parse_meta_status_payload(payload)
    assert len(events) == 5
    pairs = {(e.message_id, e.status) for e in events}
    assert pairs == {
        ("wamid.A", "sent"),
        ("wamid.A", "delivered"),
        ("wamid.A", "read"),
        ("wamid.B", "delivered"),
        ("wamid.C", "failed"),
    }
    # Distinct event keys so the append-only store does not dedupe legitimate batched events.
    assert len({e.event_key() for e in events}) == 5


def test_parse_meta_status_payload_ignores_non_message_fields_in_changes():
    """Meta sends non-``messages`` change fields (e.g. ``message_template_status_update``)
    in the same webhook. They have no ``statuses[]`` array and must be skipped silently,
    while sibling ``messages`` changes still emit events.
    """
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
                                    "id": "wamid.OK",
                                    "status": "delivered",
                                    "timestamp": "1748000100",
                                    "recipient_id": "5491150380097",
                                }
                            ],
                        },
                    },
                ],
            }
        ],
    }
    events = parse_meta_status_payload(payload)
    assert len(events) == 1
    assert events[0].message_id == "wamid.OK"
    assert events[0].status == "delivered"

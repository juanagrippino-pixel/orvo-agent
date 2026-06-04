"""Append-only store for WhatsApp delivery status webhook events.

Meta WhatsApp Cloud API delivers per-message lifecycle events
(``sent``, ``delivered``, ``read``, ``failed``) under
``entry[].changes[].value.statuses[]``. These events are observability data:
they tell the control plane what actually happened to messages we dispatched,
which is something Graph API ``200 OK`` cannot guarantee.

Run ledger terminal records are immutable, so we keep these in a dedicated,
append-only table keyed by a deterministic event key. Meta retries webhook
delivery; the dedup key absorbs duplicates without raising.

This module is intentionally generic across provider strings ("meta_cloud",
"twilio", ...). For now only the Meta Cloud parser is implemented.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

from pydantic import BaseModel, Field, field_validator

from app.brain.security.redaction import redact_secrets


META_PROVIDER = "meta_cloud"


def _now_utc_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def build_event_key(*, provider: str, message_id: str, status: str, timestamp: str | None) -> str:
    """Deterministic dedup key for a single status event.

    Meta retries webhook delivery with identical payloads, so any combination
    of ``(provider, message_id, status, timestamp)`` represents the same event.
    """

    return f"{provider}|{message_id}|{status}|{timestamp or ''}"


class WhatsAppDeliveryStatusEvent(BaseModel):
    """One delivery status event for a single outbound message."""

    provider: str = Field(..., min_length=1)
    message_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    status_timestamp: str | None = None
    recipient_id: str | None = None
    business_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("raw", mode="before")
    @classmethod
    def redact_raw(cls, value: Any) -> dict[str, Any]:
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            return {}
        redacted = redact_secrets(value)
        if not isinstance(redacted, dict):
            return {}
        return redacted

    def event_key(self) -> str:
        return build_event_key(
            provider=self.provider,
            message_id=self.message_id,
            status=self.status,
            timestamp=self.status_timestamp,
        )


class SQLiteWhatsAppDeliveryStatusStore:
    """Append-only SQLite store for WhatsApp delivery status events.

    Schema is created by :func:`app.brain.storage.init_schema`. Duplicate
    event keys are ignored (``INSERT OR IGNORE``) so retried webhooks are safe.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def record_event(self, event: WhatsAppDeliveryStatusEvent) -> None:
        created_at = _now_utc_iso()
        data = json.dumps(event.model_dump(mode="json"), sort_keys=True)
        self._conn.execute(
            """
            INSERT OR IGNORE INTO whatsapp_delivery_status_events (
                event_key, provider, message_id, status, recipient_id,
                business_id, status_timestamp, created_at, data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_key(),
                event.provider,
                event.message_id,
                event.status,
                event.recipient_id,
                event.business_id,
                event.status_timestamp,
                created_at,
                data,
            ),
        )
        self._conn.commit()

    def record_events(self, events: Iterable[WhatsAppDeliveryStatusEvent]) -> int:
        count = 0
        for event in events:
            self.record_event(event)
            count += 1
        return count

    def list_recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if limit < 1:
            limit = 1
        cursor = self._conn.execute(
            """
            SELECT provider, message_id, status, recipient_id, business_id,
                   status_timestamp, created_at, data
            FROM whatsapp_delivery_status_events
            ORDER BY created_at DESC, message_id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            provider, message_id, status, recipient_id, business_id, status_ts, created_at, data = row
            try:
                raw = json.loads(data).get("raw", {})
            except (TypeError, ValueError):
                raw = {}
            result.append(
                {
                    "provider": provider,
                    "message_id": message_id,
                    "status": status,
                    "recipient_id": recipient_id,
                    "business_id": business_id,
                    "status_timestamp": status_ts,
                    "created_at": created_at,
                    "raw": redact_secrets(raw),
                }
            )
        return result


def parse_meta_status_payload(payload: Any) -> list[WhatsAppDeliveryStatusEvent]:
    """Extract delivery status events from a Meta WhatsApp Cloud webhook payload.

    Tolerates malformed shapes: returns ``[]`` instead of raising. Status
    entries missing ``id`` or ``status`` are skipped silently.
    """

    if not isinstance(payload, dict):
        return []
    events: list[WhatsAppDeliveryStatusEvent] = []
    for entry in _safe_iter(payload.get("entry")):
        if not isinstance(entry, dict):
            continue
        for change in _safe_iter(entry.get("changes")):
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            statuses = value.get("statuses")
            if not isinstance(statuses, list):
                continue
            for status_entry in statuses:
                if not isinstance(status_entry, dict):
                    continue
                message_id = status_entry.get("id")
                status = status_entry.get("status")
                if not isinstance(message_id, str) or not message_id:
                    continue
                if not isinstance(status, str) or not status:
                    continue
                timestamp = status_entry.get("timestamp")
                recipient_id = status_entry.get("recipient_id")
                try:
                    events.append(
                        WhatsAppDeliveryStatusEvent(
                            provider=META_PROVIDER,
                            message_id=message_id,
                            status=status,
                            status_timestamp=str(timestamp) if timestamp is not None else None,
                            recipient_id=str(recipient_id) if isinstance(recipient_id, (str, int)) else None,
                            raw=status_entry,
                        )
                    )
                except Exception:
                    # Never let one malformed status entry crash the webhook.
                    continue
    return events


def _safe_iter(value: Any) -> Iterable[Any]:
    if isinstance(value, list):
        return value
    return ()

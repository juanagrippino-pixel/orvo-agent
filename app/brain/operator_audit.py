"""Append-only internal operator audit log helpers.

The audit log records security-relevant internal operator actions without making
HTTP routes or operator projections a source of truth. Payloads are redacted at
write time so raw credentials from operator comments/metadata cannot be
persisted accidentally.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.brain.security.redaction import redact_secrets, redact_text


class SQLiteOperatorAuditStore:
    """SQLite-backed append-only audit store for internal operator actions."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def append_event(
        self,
        *,
        business_id: str,
        actor_ref: str,
        event_type: str,
        target_type: str,
        target_id: str | None = None,
        request_id: str | None = None,
        data: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> str:
        """Persist one redacted audit event and return its event id."""

        event_id = f"audit_{uuid4().hex}"
        captured_at = created_at or datetime.now(timezone.utc)
        safe_data = redact_secrets(data or {})
        if not isinstance(safe_data, dict):
            safe_data = {"value": safe_data}
        self._conn.execute(
            """
            INSERT INTO operator_audit_events (
                event_id, business_id, actor_ref, event_type, target_type,
                target_id, request_id, created_at, data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                redact_text(business_id) or "[REDACTED]",
                redact_text(actor_ref) or "[REDACTED]",
                redact_text(event_type) or "operator_event",
                redact_text(target_type) or "unknown",
                redact_text(target_id) if target_id is not None else None,
                redact_text(request_id) if request_id is not None else None,
                captured_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                json.dumps(safe_data, sort_keys=True, separators=(",", ":")),
            ),
        )
        self._conn.commit()
        return event_id

    def list_events(self, *, business_id: str, limit: int) -> list[dict[str, Any]]:
        """Return newest audit events for one business with payloads redacted.

        The store keeps reads scoped by ``business_id`` so operator/API callers
        cannot accidentally page across tenant boundaries. ``limit`` is expected
        to be validated by the service layer before it reaches storage.
        """

        rows = self._conn.execute(
            """
            SELECT event_id, business_id, actor_ref, event_type, target_type,
                   target_id, request_id, created_at, data
            FROM operator_audit_events
            WHERE business_id = ?
            ORDER BY created_at DESC, event_id DESC
            LIMIT ?
            """,
            (business_id, limit),
        ).fetchall()
        events: list[dict[str, Any]] = []
        for (
            event_id,
            row_business_id,
            actor_ref,
            event_type,
            target_type,
            target_id,
            request_id,
            created_at,
            raw_data,
        ) in rows:
            try:
                data = json.loads(raw_data)
            except (TypeError, json.JSONDecodeError):
                data = {"value": raw_data}
            events.append(
                redact_secrets(
                    {
                        "event_id": event_id,
                        "business_id": row_business_id,
                        "actor_ref": actor_ref,
                        "event_type": event_type,
                        "target_type": target_type,
                        "target_id": target_id,
                        "request_id": request_id,
                        "created_at": created_at,
                        "data": data,
                    }
                )
            )
        return events

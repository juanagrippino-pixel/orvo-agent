"""Durable audit helpers for internal operator security events.

Packet O audit events record denied/failed internal operator actions without
turning operator projections into source-of-truth state. Payload data is redacted
before persistence so audit durability never stores raw credentials.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.brain.security.redaction import redact_secrets, redact_text


DEFAULT_OPERATOR_AUDIT_RETENTION_DAYS = 90
MAX_OPERATOR_AUDIT_RETENTION_DAYS = 90


class OperatorAuditExportError(Exception):
    """Safe error raised for invalid operator-audit export controls."""

    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        self.code = code
        self.message = redact_text(message) or "Operator audit export error"
        self.status_code = status_code
        super().__init__(self.message)


def parse_audit_retention_days(
    value: str | None,
    *,
    default: int = DEFAULT_OPERATOR_AUDIT_RETENTION_DAYS,
    max_days: int = MAX_OPERATOR_AUDIT_RETENTION_DAYS,
) -> int:
    """Return a bounded retention window for admin audit exports.

    Audit events are durable, but operator-facing exports must remain bounded so
    an overbroad admin query cannot accidentally expose historical tenant
    activity beyond the approved operational window.
    """

    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise OperatorAuditExportError(
            "invalid_retention_days",
            "retention_days must be an integer",
            status_code=400,
        ) from exc
    if parsed < 1:
        raise OperatorAuditExportError(
            "invalid_retention_days",
            "retention_days must be positive",
            status_code=400,
        )
    if parsed > max_days:
        raise OperatorAuditExportError(
            "invalid_retention_days",
            f"retention_days must be <= {max_days}",
            status_code=400,
        )
    return parsed


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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

    def list_events(
        self,
        *,
        business_id: str,
        limit: int = 100,
        retention_days: int = DEFAULT_OPERATOR_AUDIT_RETENTION_DAYS,
    ) -> list[dict[str, Any]]:
        """Return newest audit events for one business with payloads redacted."""

        cutoff = (_utc_now() - timedelta(days=retention_days)).isoformat().replace("+00:00", "Z")

        rows = self._conn.execute(
            """
            SELECT event_id, business_id, actor_ref, event_type, target_type,
                   target_id, request_id, created_at, data
            FROM operator_audit_events
            WHERE business_id = ? AND created_at >= ?
            ORDER BY created_at DESC, event_id DESC
            LIMIT ?
            """,
            (business_id, cutoff, limit),
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

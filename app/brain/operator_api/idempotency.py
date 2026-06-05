from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.brain.audit_scope import audit_business_scope_key
from app.brain.security.redaction import redact_secrets, redact_text

from .common import OperatorAPIError


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def case_action_payload_fingerprint(
    *,
    business_id: str,
    case_id: str,
    action_key: str,
    actor_ref: str,
    payload: dict[str, Any],
) -> str:
    """Return a non-secret fingerprint for one operator case-action attempt."""

    digest_payload = {
        "business_id": business_id,
        "case_id": case_id,
        "action_key": action_key,
        "actor_ref": actor_ref,
        "payload": payload,
    }
    return hashlib.sha256(_stable_json(digest_payload).encode("utf-8")).hexdigest()


def _idempotency_key_hash(*, business_id: str, idempotency_key: str) -> str:
    digest_payload = {
        "business_scope_key": audit_business_scope_key(business_id),
        "idempotency_key": idempotency_key,
    }
    return hashlib.sha256(_stable_json(digest_payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CaseActionIdempotencyReservation:
    replayed_data: dict[str, Any] | None = None

    @property
    def is_replay(self) -> bool:
        return self.replayed_data is not None


class SQLiteCaseActionIdempotencyStore:
    """Durable idempotency reservations for mutating operator case actions."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def reserve(
        self,
        *,
        business_id: str,
        idempotency_key: str,
        case_id: str,
        action_key: str,
        actor_ref: str,
        payload_fingerprint: str,
    ) -> CaseActionIdempotencyReservation:
        key_hash = _idempotency_key_hash(business_id=business_id, idempotency_key=idempotency_key)
        now = _now_iso()
        safe_actor_ref = redact_text(actor_ref) or "[REDACTED]"
        try:
            self._conn.execute(
                """
                INSERT INTO operator_case_action_idempotency (
                    business_scope_key, idempotency_key_hash, business_id, case_id,
                    action_key, actor_ref, payload_fingerprint, status,
                    response_data, status_code, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'started', NULL, NULL, ?, ?)
                """,
                (
                    audit_business_scope_key(business_id),
                    key_hash,
                    business_id,
                    case_id,
                    action_key,
                    safe_actor_ref,
                    payload_fingerprint,
                    now,
                    now,
                ),
            )
            self._conn.commit()
            return CaseActionIdempotencyReservation()
        except sqlite3.IntegrityError:
            row = self._conn.execute(
                """
                SELECT case_id, action_key, actor_ref, payload_fingerprint, status, response_data
                FROM operator_case_action_idempotency
                WHERE business_scope_key = ? AND idempotency_key_hash = ?
                """,
                (audit_business_scope_key(business_id), key_hash),
            ).fetchone()
            if row is None:
                raise OperatorAPIError(
                    "case_action_idempotency_conflict",
                    "case action idempotency reservation conflicted",
                    status_code=409,
                )
            (
                existing_case_id,
                existing_action_key,
                existing_actor_ref,
                existing_payload_fingerprint,
                existing_status,
                raw_response_data,
            ) = row
            if (
                existing_case_id != case_id
                or existing_action_key != action_key
                or existing_actor_ref != safe_actor_ref
                or existing_payload_fingerprint != payload_fingerprint
            ):
                raise OperatorAPIError(
                    "case_action_idempotency_key_reused",
                    "idempotency key was already used for a different case action",
                    status_code=409,
                )
            if existing_status == "completed" and raw_response_data:
                try:
                    replayed = json.loads(raw_response_data)
                except json.JSONDecodeError as exc:
                    raise OperatorAPIError(
                        "case_action_idempotency_replay_unavailable",
                        "idempotent case action replay is unavailable",
                        status_code=409,
                    ) from exc
                if isinstance(replayed, dict):
                    return CaseActionIdempotencyReservation(replayed_data=replayed)
            raise OperatorAPIError(
                "case_action_idempotency_in_progress",
                "case action with this idempotency key is still in progress",
                status_code=409,
            )

    def complete(
        self,
        *,
        business_id: str,
        idempotency_key: str,
        response_data: dict[str, Any],
        status_code: int = 200,
    ) -> None:
        safe_response = redact_secrets(response_data)
        if not isinstance(safe_response, dict):
            safe_response = {"value": safe_response}
        self._conn.execute(
            """
            UPDATE operator_case_action_idempotency
            SET status = 'completed', response_data = ?, status_code = ?, updated_at = ?
            WHERE business_scope_key = ? AND idempotency_key_hash = ?
            """,
            (
                _stable_json(safe_response),
                status_code,
                _now_iso(),
                audit_business_scope_key(business_id),
                _idempotency_key_hash(business_id=business_id, idempotency_key=idempotency_key),
            ),
        )
        self._conn.commit()


__all__ = [name for name in globals() if not name.startswith("__")]

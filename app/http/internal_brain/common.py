from __future__ import annotations

import hmac
import os
import sqlite3
from contextlib import closing
from uuid import uuid4

from flask import jsonify, request

from app.brain.operator_api import OperatorAPIError
from app.brain.operator_audit import SQLiteOperatorAuditStore

from app.brain.operator_auth import (
    INTERNAL_READ_PERMISSION,
    InternalOperatorAuthorizationError,
    build_internal_operator_principal,
    permissions_for_role,
    require_internal_permission,
)
from app.brain.security.redaction import redact_secrets, redact_text
from app.brain.storage import SQLiteOperationalCaseStore, SQLiteRunLedger, init_schema


def _internal_request_id() -> str:
    return request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"


def _internal_success(business_id: str, data: dict, *, warnings: list[str] | None = None):
    return jsonify(
        {
            "ok": True,
            "business_id": business_id,
            "request_id": _internal_request_id(),
            "data": data,
            "warnings": warnings or [],
            "redaction_applied": True,
        }
    )


def _internal_error(business_id: str, code: str, message: str, *, status_code: int):
    return (
        jsonify(
            {
                "ok": False,
                "business_id": business_id,
                "request_id": _internal_request_id(),
                "error": {"code": code, "message": message, "safe_to_show_owner": False},
                "redaction_applied": True,
            }
        ),
        status_code,
    )


def _public_error_text(exc: Exception) -> str:
    redacted = redact_text(str(exc))
    if not redacted:
        return "[REDACTED]"
    return str(redact_secrets(redacted))


def _public_error_response(payload: dict, status_code: int):
    return jsonify(redact_secrets(payload)), status_code


def _authorize_internal_operator(business_id: str):
    expected = os.environ.get("ORVO_INTERNAL_OPERATOR_TOKEN", "")
    if not expected:
        return _internal_error(
            business_id,
            "internal_auth_not_configured",
            "Internal operator API token is not configured.",
            status_code=503,
        )
    supplied = request.headers.get("Authorization", "")
    if not hmac.compare_digest(supplied, f"Bearer {expected}"):
        return _internal_error(business_id, "unauthorized", "Unauthorized", status_code=401)
    return None


def _internal_brain_db_path() -> str:
    return os.environ.get("ORVO_BRAIN_DB_PATH", "orvo_brain.sqlite3")


def _append_operator_audit_event(
    *,
    business_id: str,
    actor_ref: str,
    event_type: str,
    target_type: str,
    target_id: str | None = None,
    data: dict | None = None,
):
    """Append a redacted operator audit event using the durable Brain DB."""

    with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
        init_schema(conn)
        SQLiteOperatorAuditStore(conn).append_event(
            business_id=business_id,
            actor_ref=actor_ref,
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            request_id=_internal_request_id(),
            data=data or {},
        )


def _internal_principal_or_error(business_id: str, permission: str):
    try:
        principal = build_internal_operator_principal(
            actor_ref=request.headers.get("X-Orvo-Operator", ""),
            role=request.headers.get("X-Orvo-Role"),
        )
        require_internal_permission(principal, permission)
    except InternalOperatorAuthorizationError as exc:
        return None, _internal_error(business_id, "forbidden", "Forbidden", status_code=exc.status_code)
    return principal, None


def _require_internal_header_permission(business_id: str, permission: str):
    _principal, permission_error = _internal_principal_or_error(business_id, permission)
    return permission_error

def _with_internal_stores(business_id: str, handler):
    auth_error = _authorize_internal_operator(business_id)
    if auth_error is not None:
        return auth_error
    permission_error = _require_internal_header_permission(business_id, INTERNAL_READ_PERMISSION)
    if permission_error is not None:
        return permission_error
    try:
        with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
            init_schema(conn)
            return handler(SQLiteOperationalCaseStore(conn), SQLiteRunLedger(conn))
    except OperatorAPIError as exc:
        return _internal_error(business_id, exc.code, exc.message, status_code=exc.status_code)

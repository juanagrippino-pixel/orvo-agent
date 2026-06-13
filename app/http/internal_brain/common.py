from __future__ import annotations

import hmac
import os
import re
import sqlite3
from contextlib import closing
from typing import Any
from uuid import uuid4

from flask import jsonify, request

from app.brain.operator_api import OperatorAPIError
from app.brain.operator_audit import SQLiteOperatorAuditStore

from app.brain.operator_auth import (
    INTERNAL_READ_PERMISSION,
    InternalOperatorAuthorizationError,
    audit_safe_business_values,
    audit_safe_operator_role,
    build_internal_operator_principal,
    require_explicit_global_business_scope,
    require_internal_business_scope,
    require_internal_permission,
)
from app.brain.security.redaction import redact_secrets, redact_text
from app.brain.storage import SQLiteOperationalCaseStore, SQLiteRunLedger, init_schema


_MAX_INTERNAL_REQUEST_ID_LENGTH = 128
_MAX_INTERNAL_ERROR_CODE_LENGTH = 80
_INTERNAL_ERROR_CODE_RE = re.compile(r"^[a-z][a-z0-9_.-]*$")


def _safe_internal_business_id(business_id: str) -> str:
    """Return a route business id safe for internal API envelopes.

    Normal business ids are operational routing labels and remain visible. If a
    pasted credential lands in the path parameter, collapse the whole label so
    the response cannot echo secret tails before auth or in success projections.
    """

    redacted = redact_text(business_id) or "[REDACTED]"
    return "[REDACTED]" if redacted != business_id or "[REDACTED]" in business_id else redacted


def _collapse_business_id_fields(value: Any) -> Any:
    """Collapse secret-shaped business_id fields after normal redaction.

    Internal projections reuse ``business_id`` as both a scoping field and a
    display label. Reusing the same boundary helper here prevents nested
    projections from leaking partial key-value labels such as
    ``tenant access_token=[REDACTED]``.
    """

    if isinstance(value, dict):
        collapsed: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if key == "business_id" and isinstance(raw_value, str):
                collapsed[key] = _safe_internal_business_id(raw_value)
            else:
                collapsed[key] = _collapse_business_id_fields(raw_value)
        return collapsed
    if isinstance(value, list):
        return [_collapse_business_id_fields(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_collapse_business_id_fields(item) for item in value)
    return value


def _internal_request_id() -> str:
    supplied = request.headers.get("X-Request-ID")
    if supplied is None or not supplied.strip():
        return f"req_{uuid4().hex}"
    candidate = supplied.strip()
    if len(candidate) > _MAX_INTERNAL_REQUEST_ID_LENGTH:
        return "[REDACTED]"
    redacted = redact_text(candidate) or "[REDACTED]"
    return redacted if redacted == candidate else "[REDACTED]"


def _internal_success(business_id: str, data: dict, *, warnings: list[str] | None = None):
    return jsonify(
        {
            "ok": True,
            "business_id": _safe_internal_business_id(business_id),
            "request_id": _internal_request_id(),
            "data": _collapse_business_id_fields(redact_secrets(data)),
            "warnings": redact_secrets(warnings or []),
            "redaction_applied": True,
        }
    )


def _safe_internal_error_code(code: str) -> str:
    """Return a stable internal error code safe for JSON envelopes.

    Route handlers normally pass static lowercase codes. If a dynamic exception
    code, pasted credential, oversized value, or display text reaches this
    boundary, collapse it to a generic code so the response cannot echo
    caller-controlled/secret-shaped tails.
    """

    candidate = redact_text(code) or "internal_error"
    if candidate != code:
        return "internal_error"
    if len(candidate) > _MAX_INTERNAL_ERROR_CODE_LENGTH:
        return "internal_error"
    if _INTERNAL_ERROR_CODE_RE.fullmatch(candidate) is None:
        return "internal_error"
    return candidate


def _internal_error(business_id: str, code: str, message: str, *, status_code: int):
    safe_message = redact_text(message) or "[REDACTED]"
    safe_message = str(redact_secrets(safe_message))
    return (
        jsonify(
            {
                "ok": False,
                "business_id": _safe_internal_business_id(business_id),
                "request_id": _internal_request_id(),
                "error": {
                    "code": _safe_internal_error_code(code),
                    "message": safe_message,
                    "safe_to_show_owner": False,
                },
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


def _authorization_scheme(value: str) -> str | None:
    if not value.strip():
        return None
    scheme = value.strip().split(None, 1)[0]
    return redact_text(scheme) or "[REDACTED]"


def _constant_time_text_equals(left: str, right: str) -> bool:
    """Compare header strings without raising on non-ASCII probe values."""

    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _record_internal_authentication_denial(*, business_id: str, actor_ref: str, supplied_authorization: str):
    """Best-effort audit for failed internal bearer-token authentication.

    The raw Authorization header is intentionally not persisted; only safe shape
    metadata is kept so operators can investigate auth abuse without leaking
    bearer-token tails into the durable audit log. Missing-header probes are
    audited too because they still exercise the internal auth boundary.
    """

    header_present = bool(supplied_authorization)
    try:
        _append_operator_audit_event(
            business_id=business_id,
            actor_ref=actor_ref or "anonymous",
            event_type="operator.authentication.denied",
            target_type="internal_operator_api",
            target_id=business_id,
            data={
                "status": "denied",
                "reason": "invalid_internal_token" if header_present else "missing_internal_token",
                "method": request.method,
                "header_present": header_present,
                "scheme": _authorization_scheme(supplied_authorization),
            },
        )
    except Exception:
        # Authentication must still fail closed even if the audit sink is
        # temporarily unavailable. Do not expose persistence details to callers.
        return


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
    if not _constant_time_text_equals(supplied, f"Bearer {expected}"):
        _record_internal_authentication_denial(
            business_id=business_id,
            actor_ref=request.headers.get("X-Orvo-Operator", ""),
            supplied_authorization=supplied,
        )
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


def _internal_operator_businesses_header() -> str | None:
    if "X-Orvo-Businesses" not in request.headers:
        return None
    return request.headers.get("X-Orvo-Businesses", "")


def _authorization_denial_data(exc: InternalOperatorAuthorizationError) -> dict:
    data = {
        "status": "denied",
        "reason": exc.code,
        "status_code": exc.status_code,
        "method": request.method,
        "role": audit_safe_operator_role(exc.role),
        "permission": exc.permission,
    }
    safe_allowed_businesses = audit_safe_business_values(exc.allowed_businesses)
    if safe_allowed_businesses is not None:
        data["allowed_businesses"] = safe_allowed_businesses
    return data


def _record_internal_authorization_denial(*, business_id: str, actor_ref: str, exc: InternalOperatorAuthorizationError):
    _append_operator_audit_event(
        business_id=business_id,
        actor_ref=actor_ref,
        event_type="operator.authorization.denied",
        target_type="internal_operator_api",
        target_id=business_id,
        data=_authorization_denial_data(exc),
    )


def _internal_principal_or_error(
    business_id: str,
    permission: str,
    *,
    audit_denial: bool = False,
    require_explicit_global_scope: bool = False,
):
    actor_ref = request.headers.get("X-Orvo-Operator", "")
    try:
        principal = build_internal_operator_principal(
            actor_ref=actor_ref,
            role=request.headers.get("X-Orvo-Role"),
            allowed_businesses_header=_internal_operator_businesses_header(),
        )
        if require_explicit_global_scope:
            require_internal_permission(principal, permission)
            require_explicit_global_business_scope(principal)
        else:
            require_internal_business_scope(principal, business_id)
            require_internal_permission(principal, permission)
    except InternalOperatorAuthorizationError as exc:
        if audit_denial:
            _record_internal_authorization_denial(business_id=business_id, actor_ref=actor_ref or "anonymous", exc=exc)
        return None, _internal_error(business_id, "forbidden", "Forbidden", status_code=exc.status_code)
    return principal, None


def _require_internal_header_permission(business_id: str, permission: str, *, audit_denial: bool = False):
    _principal, permission_error = _internal_principal_or_error(business_id, permission, audit_denial=audit_denial)
    return permission_error

def _with_internal_stores(business_id: str, handler):
    auth_error = _authorize_internal_operator(business_id)
    if auth_error is not None:
        return auth_error
    permission_error = _require_internal_header_permission(business_id, INTERNAL_READ_PERMISSION, audit_denial=True)
    if permission_error is not None:
        return permission_error
    try:
        with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
            init_schema(conn)
            return handler(SQLiteOperationalCaseStore(conn), SQLiteRunLedger(conn))
    except OperatorAPIError as exc:
        return _internal_error(business_id, exc.code, exc.message, status_code=exc.status_code)

from __future__ import annotations

import sqlite3
from contextlib import closing

from flask import request

from app.brain.operator_api import OperatorAPIError, parse_limit
from app.brain.operator_audit import OperatorAuditExportError, SQLiteOperatorAuditStore, parse_audit_retention_days
from app.brain.operator_auth import OPERATOR_AUDIT_READ_PERMISSION
from app.brain.storage import init_schema

from .common import (
    _append_operator_audit_event,
    _authorize_internal_operator,
    _internal_brain_db_path,
    _internal_error,
    _internal_principal_or_error,
    _internal_success,
)


def register_operator_audit_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/operator-audit-events")
    def internal_brain_operator_audit_events(business_id: str):
        auth_error = _authorize_internal_operator(business_id)
        if auth_error is not None:
            return auth_error
        principal, permission_error = _internal_principal_or_error(
            business_id,
            OPERATOR_AUDIT_READ_PERMISSION,
            audit_denial=True,
        )
        if permission_error is not None:
            return permission_error
        assert principal is not None

        raw_limit = request.args.get("limit")
        raw_retention_days = request.args.get("retention_days")

        def _audit_read_failed(*, error_code: str, status_code: int) -> None:
            try:
                _append_operator_audit_event(
                    business_id=business_id,
                    actor_ref=principal.actor_ref,
                    event_type="operator.operator_audit_events.read_failed",
                    target_type="operator_audit_events",
                    target_id=business_id,
                    data={
                        "status": "failed",
                        "scope": "business",
                        "error_code": error_code,
                        "status_code": status_code,
                        "method": request.method,
                        "limit_present": raw_limit is not None,
                        "retention_days_present": raw_retention_days is not None,
                    },
                )
            except Exception:
                # Audit failures are secondary telemetry. Never turn an export
                # denial/failure into a generic 500 or expose sink internals.
                return

        try:
            limit = parse_limit(raw_limit, default=50, max_limit=200)
            retention_days = parse_audit_retention_days(raw_retention_days)
        except OperatorAPIError as exc:
            _audit_read_failed(error_code=exc.code, status_code=exc.status_code)
            return _internal_error(business_id, exc.code, exc.message, status_code=exc.status_code)
        except OperatorAuditExportError as exc:
            _audit_read_failed(error_code=exc.code, status_code=exc.status_code)
            return _internal_error(business_id, exc.code, exc.message, status_code=exc.status_code)

        try:
            with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
                init_schema(conn)
                events = SQLiteOperatorAuditStore(conn).list_events(
                    business_id=business_id,
                    limit=limit,
                    retention_days=retention_days,
                )
        except sqlite3.Error:
            _audit_read_failed(error_code="internal_store_unavailable", status_code=503)
            return _internal_error(
                business_id,
                "internal_store_unavailable",
                "Internal store unavailable.",
                status_code=503,
            )

        try:
            _append_operator_audit_event(
                business_id=business_id,
                actor_ref=principal.actor_ref,
                event_type="operator.operator_audit_events.read",
                target_type="operator_audit_events",
                target_id=business_id,
                data={
                    "status": "allowed",
                    "scope": "business",
                    "limit": limit,
                    "retention_days": retention_days,
                    "result_count": len(events),
                },
            )
        except Exception:
            # The export result is already authorized and read. Do not fail the
            # response because the secondary audit append failed.
            pass
        return _internal_success(
            business_id,
            {
                "events": events,
                "count": len(events),
                "limit": limit,
                "retention_days": retention_days,
            },
        )

from __future__ import annotations

import sqlite3
from contextlib import closing

from flask import request

from app.brain.operator_api import OperatorAPIError, parse_limit
from app.brain.operator_audit import OperatorAuditExportError, SQLiteOperatorAuditStore, parse_audit_retention_days
from app.brain.operator_auth import OPERATOR_AUDIT_READ_PERMISSION
from app.brain.storage import init_schema

from .common import (
    _authorize_internal_operator,
    _internal_brain_db_path,
    _internal_error,
    _internal_success,
    _require_internal_header_permission,
)


def register_operator_audit_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/operator-audit-events")
    def internal_brain_operator_audit_events(business_id: str):
        auth_error = _authorize_internal_operator(business_id)
        if auth_error is not None:
            return auth_error
        permission_error = _require_internal_header_permission(
            business_id,
            OPERATOR_AUDIT_READ_PERMISSION,
            audit_denial=True,
        )
        if permission_error is not None:
            return permission_error
        try:
            limit = parse_limit(request.args.get("limit"), default=50, max_limit=200)
            retention_days = parse_audit_retention_days(request.args.get("retention_days"))
        except OperatorAPIError as exc:
            return _internal_error(business_id, exc.code, exc.message, status_code=exc.status_code)
        except OperatorAuditExportError as exc:
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
            return _internal_error(
                business_id,
                "internal_store_unavailable",
                "Internal store unavailable.",
                status_code=503,
            )
        return _internal_success(
            business_id,
            {
                "events": events,
                "count": len(events),
                "limit": limit,
                "retention_days": retention_days,
            },
        )

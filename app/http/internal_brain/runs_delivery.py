from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from app.brain.operator_api import *  # noqa: F401,F403
from app.brain.operator_auth import CASE_ACTION_PERMISSION, INTERNAL_READ_PERMISSION

from .common import (
    _authorize_internal_operator,
    _internal_success,
    _internal_error,
    _internal_principal_or_error,
    _require_internal_header_permission,
    _with_internal_stores,
)

import sqlite3
from contextlib import closing

from app.brain.delivery_status import SQLiteWhatsAppDeliveryStatusStore
from app.brain.storage import init_schema
from .common import _internal_brain_db_path


def register_run_delivery_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/runs")
    def internal_brain_runs(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_run_history(
                    run_ledger,
                    business_id=business_id,
                    status=request.args.get("status"),
                    limit=request.args.get("limit"),
                ),
            ),
        )


    @app.get("/internal/brain/whatsapp/delivery-statuses")
    def internal_brain_whatsapp_delivery_statuses():
        business_id = "whatsapp"
        auth_error = _authorize_internal_operator(business_id)
        if auth_error is not None:
            return auth_error
        permission_error = _require_internal_header_permission(business_id, INTERNAL_READ_PERMISSION)
        if permission_error is not None:
            return permission_error
        raw_limit = request.args.get("limit")
        try:
            limit = int(raw_limit) if raw_limit not in (None, "") else 50
        except ValueError:
            return _internal_error(business_id, "invalid_limit", "limit must be an integer", status_code=400)
        if limit < 1:
            return _internal_error(business_id, "invalid_limit", "limit must be positive", status_code=400)
        limit = min(limit, 200)
        with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
            init_schema(conn)
            events = SQLiteWhatsAppDeliveryStatusStore(conn).list_recent(limit=limit)
        return _internal_success(business_id, {"events": redact_secrets(events)})


    @app.get("/internal/brain/businesses/<business_id>/runs/<run_id>")
    def internal_brain_run_detail(business_id: str, run_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                get_run_projection(run_ledger, business_id=business_id, run_id=run_id),
            ),
        )

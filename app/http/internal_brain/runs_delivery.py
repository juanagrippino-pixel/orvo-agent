from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from app.brain.operator_api import *  # noqa: F401,F403
from app.brain.operator_auth import OPERATOR_AUDIT_READ_PERMISSION

from .common import (
    _authorize_internal_operator,
    _internal_success,
    _internal_error,
    _internal_principal_or_error,
    _with_internal_stores,
    _append_operator_audit_event,
)

import sqlite3
from contextlib import closing

from app.brain.delivery_status import SQLiteWhatsAppDeliveryStatusStore, normalize_delivery_status_filter
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
                    trigger_type=request.args.get("trigger_type"),
                    limit=request.args.get("limit"),
                    dispatch_status=request.args.get("dispatch_status"),
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/runs/dispatch-status-summary")
    def internal_brain_run_dispatch_status_summary(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_run_dispatch_statuses(
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
        principal, permission_error = _internal_principal_or_error(
            business_id,
            OPERATOR_AUDIT_READ_PERMISSION,
            audit_denial=True,
            require_explicit_global_scope=True,
        )
        if permission_error is not None:
            return permission_error
        assert principal is not None
        raw_limit = request.args.get("limit")
        raw_status = request.args.get("status")
        try:
            limit = parse_limit(raw_limit, default=50, max_limit=200)
            status_filter = normalize_delivery_status_filter(raw_status)
        except OperatorAPIError as exc:
            _append_operator_audit_event(
                business_id=business_id,
                actor_ref=principal.actor_ref,
                event_type="operator.whatsapp_delivery_statuses.read_failed",
                target_type="whatsapp_delivery_statuses",
                target_id=business_id,
                data={
                    "status": "failed",
                    "scope": "global",
                    "error_code": exc.code,
                    "status_code": exc.status_code,
                    "limit_present": raw_limit is not None,
                    "status_filter_present": raw_status is not None,
                },
            )
            return _internal_error(business_id, exc.code, exc.message, status_code=exc.status_code)
        except ValueError:
            _append_operator_audit_event(
                business_id=business_id,
                actor_ref=principal.actor_ref,
                event_type="operator.whatsapp_delivery_statuses.read_failed",
                target_type="whatsapp_delivery_statuses",
                target_id=business_id,
                data={
                    "status": "failed",
                    "scope": "global",
                    "error_code": "invalid_delivery_status",
                    "status_code": 400,
                    "status_filter_present": raw_status is not None,
                },
            )
            return _internal_error(business_id, "invalid_delivery_status", "unsupported delivery status", status_code=400)
        with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
            init_schema(conn)
            events = SQLiteWhatsAppDeliveryStatusStore(conn).list_recent(limit=limit, status=status_filter)
        audit_data = {"status": "allowed", "scope": "global", "limit": limit}
        if status_filter is not None:
            audit_data["status_filter"] = status_filter
        _append_operator_audit_event(
            business_id=business_id,
            actor_ref=principal.actor_ref,
            event_type="operator.whatsapp_delivery_statuses.read",
            target_type="whatsapp_delivery_statuses",
            target_id=business_id,
            data=audit_data,
        )
        return _internal_success(business_id, {"events": redact_secrets(events)})


    @app.get("/internal/brain/businesses/<business_id>/runs/summary")
    def internal_brain_runs_summary(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                summarize_run_history(
                    run_ledger,
                    business_id=business_id,
                    status=request.args.get("status"),
                    trigger_type=request.args.get("trigger_type"),
                    limit=request.args.get("limit"),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/runs/<run_id>")
    def internal_brain_run_detail(business_id: str, run_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                get_run_projection(run_ledger, business_id=business_id, run_id=run_id),
            ),
        )

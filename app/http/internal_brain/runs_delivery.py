from __future__ import annotations

import sqlite3
from contextlib import closing

from flask import request

from app.brain.delivery_status import SQLiteWhatsAppDeliveryStatusStore
from app.brain.operator_api import *  # noqa: F401,F403
from app.brain.operator_auth import INTERNAL_READ_PERMISSION, OPERATOR_AUDIT_READ_PERMISSION
from app.brain.storage import init_schema

from .common import (
    _append_operator_audit_event,
    _authorize_internal_operator,
    _internal_brain_db_path,
    _internal_error,
    _internal_principal_or_error,
    _internal_success,
    _with_internal_stores,
)


def _delivery_status_limit_or_error(business_id: str):
    raw_limit = request.args.get("limit")
    try:
        limit = int(raw_limit) if raw_limit not in (None, "") else 50
    except ValueError:
        return None, _internal_error(business_id, "invalid_limit", "limit must be an integer", status_code=400)
    if limit < 1:
        return None, _internal_error(business_id, "invalid_limit", "limit must be positive", status_code=400)
    return min(limit, 200), None


def _delivery_status_success(business_id: str, *, event_business_id: str | None = None):
    limit, limit_error = _delivery_status_limit_or_error(business_id)
    if limit_error is not None:
        return limit_error
    assert limit is not None
    with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
        init_schema(conn)
        events = SQLiteWhatsAppDeliveryStatusStore(conn).list_recent(
            limit=limit,
            business_id=event_business_id,
        )
    return _internal_success(business_id, {"events": redact_secrets(events)})


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
                    dispatch_status=request.args.get("dispatch_status"),
                    dispatch_message_type=request.args.get("dispatch_message_type"),
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
                    dispatch_message_type=request.args.get("dispatch_message_type"),
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
        limit, limit_error = _delivery_status_limit_or_error(business_id)
        if limit_error is not None:
            return limit_error
        assert limit is not None
        with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
            init_schema(conn)
            events = SQLiteWhatsAppDeliveryStatusStore(conn).list_recent(limit=limit)
        _append_operator_audit_event(
            business_id=business_id,
            actor_ref=principal.actor_ref,
            event_type="operator.whatsapp_delivery_statuses.read",
            target_type="whatsapp_delivery_statuses",
            target_id=business_id,
            data={"status": "allowed", "scope": "global", "limit": limit},
        )
        return _internal_success(business_id, {"events": redact_secrets(events)})

    @app.get("/internal/brain/businesses/<business_id>/whatsapp/delivery-statuses")
    def internal_brain_business_whatsapp_delivery_statuses(business_id: str):
        auth_error = _authorize_internal_operator(business_id)
        if auth_error is not None:
            return auth_error
        _principal, permission_error = _internal_principal_or_error(
            business_id,
            INTERNAL_READ_PERMISSION,
            audit_denial=True,
        )
        if permission_error is not None:
            return permission_error
        return _delivery_status_success(business_id, event_business_id=business_id)

    @app.get("/internal/brain/businesses/<business_id>/runs/<run_id>/delivery-statuses")
    def internal_brain_run_delivery_statuses(business_id: str, run_id: str):
        def _projection(_case_store, run_ledger):
            with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
                init_schema(conn)
                return _internal_success(
                    business_id,
                    get_run_delivery_status_projection(
                        run_ledger,
                        SQLiteWhatsAppDeliveryStatusStore(conn),
                        business_id=business_id,
                        run_id=run_id,
                        limit=request.args.get("limit"),
                    ),
                )

        return _with_internal_stores(business_id, _projection)

    @app.get("/internal/brain/businesses/<business_id>/runs/<run_id>")
    def internal_brain_run_detail(business_id: str, run_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                get_run_projection(run_ledger, business_id=business_id, run_id=run_id),
            ),
        )

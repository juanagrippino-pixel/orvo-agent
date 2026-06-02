from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from app.brain.operator_api import *  # noqa: F401,F403
from app.brain.operator_auth import CASE_ACTION_PERMISSION

from .common import (
    _append_operator_audit_event,
    _internal_success,
    _internal_error,
    _internal_principal_or_error,
    _require_internal_header_permission,
    _with_internal_stores,
)


def register_dashboard_view_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/dashboard")
    def internal_brain_dashboard(business_id: str):
        limit = request.args.get("limit")
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                get_operator_dashboard(
                    case_store,
                    run_ledger,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                    limit=parse_limit(limit, default=10),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/case-views")
    def internal_brain_case_views(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(business_id, list_builtin_case_views()),
        )


    @app.get("/internal/brain/businesses/<business_id>/case-views/<view_id>/cases")
    def internal_brain_case_view_cases(business_id: str, view_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                execute_builtin_case_view(
                    case_store,
                    business_id=business_id,
                    view_id=view_id,
                    limit=request.args.get("limit"),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/<case_id>")
    def internal_brain_case_detail(business_id: str, case_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                get_case_projection(case_store, business_id=business_id, case_id=case_id),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/<case_id>/timeline")
    def internal_brain_case_timeline(business_id: str, case_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_case_timeline(
                    case_store,
                    business_id=business_id,
                    case_id=case_id,
                    event_type=request.args.get("event_type"),
                    actor_type=request.args.get("actor_type"),
                    limit=request.args.get("limit"),
                ),
            ),
        )


    @app.post("/internal/brain/businesses/<business_id>/cases/<case_id>/actions")
    def internal_brain_case_action(business_id: str, case_id: str):
        payload = request.get_json(silent=True) or {}
        actor_ref = request.headers.get("X-Orvo-Operator", "")

        def _handle(case_store, run_ledger):
            permission_error = _require_internal_header_permission(business_id, CASE_ACTION_PERMISSION)
            if permission_error is not None:
                _append_operator_audit_event(
                    business_id=business_id,
                    actor_ref=actor_ref,
                    event_type="operator.case_action.denied",
                    target_type="operational_case",
                    target_id=case_id,
                    data={
                        "action_key": str(payload.get("action_key", "")),
                        "permission": CASE_ACTION_PERMISSION,
                        "status_code": 403,
                        "payload": payload,
                    },
                )
                return permission_error
            try:
                data = apply_case_action(
                    case_store,
                    business_id=business_id,
                    case_id=case_id,
                    action_key=str(payload.get("action_key", "")),
                    actor_ref=actor_ref,
                    reason=payload.get("reason"),
                    comment=payload.get("comment"),
                    metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
                    assignee_ref=payload.get("assignee_ref"),
                    owner_ref=payload.get("owner_ref"),
                )
            except OperatorAPIError as exc:
                _append_operator_audit_event(
                    business_id=business_id,
                    actor_ref=actor_ref,
                    event_type="operator.case_action.failed",
                    target_type="operational_case",
                    target_id=case_id,
                    data={
                        "action_key": str(payload.get("action_key", "")),
                        "error_code": exc.code,
                        "status_code": exc.status_code,
                        "payload": payload,
                    },
                )
                raise
            return _internal_success(business_id, data)

        return _with_internal_stores(business_id, _handle)

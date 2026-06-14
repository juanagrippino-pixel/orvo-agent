from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from app.brain.operator_api import *  # noqa: F401,F403
from app.brain.operator_auth import CASE_ACTION_PERMISSION, safe_internal_operator_actor_ref
from app.brain.workflow_action_ledger import SQLiteWorkflowActionLedgerStore

from .common import (
    _append_operator_audit_event,
    _internal_brain_db_path,
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


    @app.get("/internal/brain/businesses/<business_id>/os-snapshot")
    def internal_brain_os_snapshot(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                get_os_snapshot(
                    case_store,
                    run_ledger,
                    business_id=business_id,
                    now=datetime.now(timezone.utc),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/case-views")
    def internal_brain_case_views(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(business_id, list_builtin_case_views()),
        )


    @app.get("/internal/brain/businesses/<business_id>/case-query-fields")
    def internal_brain_case_query_fields(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_case_query_fields(field=request.args.get("field")),
            ),
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
                    as_of=request.args.get("as_of"),
                ),
            ),
        )


    @app.get("/internal/brain/businesses/<business_id>/cases/facets")
    def internal_brain_case_facets(business_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                list_case_facets(
                    case_store,
                    business_id=business_id,
                    field=request.args.get("field"),
                    jql=request.args.get("jql"),
                    limit=request.args.get("limit"),
                    as_of=request.args.get("as_of"),
                ),
            ),
        )

    @app.get("/internal/brain/businesses/<business_id>/cases/<case_id>")
    def internal_brain_case_detail(business_id: str, case_id: str):
        return _with_internal_stores(
            business_id,
            lambda case_store, run_ledger: _internal_success(
                business_id,
                get_case_projection(case_store, business_id=business_id, case_id=case_id, as_of=request.args.get("as_of")),
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
        raw_payload = request.get_json(silent=True)
        payload = raw_payload if isinstance(raw_payload, dict) else {}
        actor_ref = safe_internal_operator_actor_ref(request.headers.get("X-Orvo-Operator", ""))

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
                        "payload": raw_payload if raw_payload is not None else payload,
                    },
                )
                return permission_error
            if raw_payload is not None and not isinstance(raw_payload, dict):
                _append_operator_audit_event(
                    business_id=business_id,
                    actor_ref=actor_ref,
                    event_type="operator.case_action.failed",
                    target_type="operational_case",
                    target_id=case_id,
                    data={
                        "action_key": "",
                        "error_code": "invalid_case_action_payload",
                        "status_code": 400,
                        "payload": raw_payload,
                    },
                )
                raise OperatorAPIError(
                    "invalid_case_action_payload",
                    "case action payload must be a JSON object",
                    status_code=400,
                )
            try:
                idempotency_key = require_case_action_idempotency_key(
                    request.headers.get("X-Idempotency-Key")
                )
                data = apply_case_action_with_idempotency(
                    case_store,
                    SQLiteWorkflowActionLedgerStore(_internal_brain_db_path()),
                    business_id=business_id,
                    case_id=case_id,
                    action_key=str(payload.get("action_key", "")),
                    idempotency_key=idempotency_key,
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

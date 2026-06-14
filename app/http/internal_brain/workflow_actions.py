from __future__ import annotations

from flask import request

from app.brain.operator_api import (
    OperatorAPIError,
    apply_case_action_with_idempotency,
    require_case_action_idempotency_key,
)
from app.brain.operator_auth import CASE_ACTION_PERMISSION, safe_internal_operator_actor_ref
from app.brain.workflow_action_ledger import SQLiteWorkflowActionLedgerStore

from .common import (
    _append_operator_audit_event,
    _internal_brain_db_path,
    _internal_success,
    _require_internal_header_permission,
    _with_internal_stores,
)


def register_case_action_routes(app):
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
                idempotency_key = require_case_action_idempotency_key(request.headers.get("X-Idempotency-Key"))
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

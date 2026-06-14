from __future__ import annotations

from flask import request

from app.brain.operator_api import OperatorAPIError, parse_limit
from app.brain.operator_auth import INTERNAL_READ_PERMISSION
from app.brain.workflow_action_audit import list_workflow_action_audit_events
from app.brain.workflow_action_ledger import SQLiteWorkflowActionLedgerStore, WorkflowActionLedgerError
from app.brain.workflow_approval_queue import list_workflow_approval_queue
from app.brain.workflow_execution_queue import list_workflow_execution_queue

from .common import (
    _authorize_internal_operator,
    _internal_brain_db_path,
    _internal_error,
    _internal_success,
    _require_internal_header_permission,
)


_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200


def _workflow_ledger() -> SQLiteWorkflowActionLedgerStore:
    return SQLiteWorkflowActionLedgerStore(_internal_brain_db_path())


def _read_limit() -> int:
    return parse_limit(request.args.get("limit"), default=_DEFAULT_LIMIT, max_limit=_MAX_LIMIT)


def _case_scope() -> str | None:
    return request.args.get("case_id")


def _action_key_scope() -> str | None:
    return request.args.get("action_key")


def _handle_projection_errors(business_id: str, exc: Exception):
    if isinstance(exc, OperatorAPIError):
        return _internal_error(business_id, exc.code, exc.message, status_code=exc.status_code)
    if isinstance(exc, WorkflowActionLedgerError):
        return _internal_error(business_id, exc.code, exc.message, status_code=400)
    raise exc


def _authorize_workflow_read(business_id: str):
    auth_error = _authorize_internal_operator(business_id)
    if auth_error is not None:
        return auth_error
    return _require_internal_header_permission(
        business_id,
        INTERNAL_READ_PERMISSION,
        audit_denial=True,
    )


def register_workflow_action_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/workflow/approval-queue")
    def internal_brain_workflow_approval_queue(business_id: str):
        access_error = _authorize_workflow_read(business_id)
        if access_error is not None:
            return access_error
        try:
            data = list_workflow_approval_queue(
                _workflow_ledger(),
                business_id=business_id,
                case_id=_case_scope(),
                action_key=_action_key_scope(),
                limit=_read_limit(),
            )
        except Exception as exc:
            return _handle_projection_errors(business_id, exc)
        return _internal_success(business_id, data)

    @app.get("/internal/brain/businesses/<business_id>/workflow/execution-queue")
    def internal_brain_workflow_execution_queue(business_id: str):
        access_error = _authorize_workflow_read(business_id)
        if access_error is not None:
            return access_error
        try:
            data = list_workflow_execution_queue(
                _workflow_ledger(),
                business_id=business_id,
                case_id=_case_scope(),
                action_key=_action_key_scope(),
                limit=_read_limit(),
            )
        except Exception as exc:
            return _handle_projection_errors(business_id, exc)
        return _internal_success(business_id, data)

    @app.get("/internal/brain/businesses/<business_id>/workflow/action-audit-events")
    def internal_brain_workflow_action_audit_events(business_id: str):
        access_error = _authorize_workflow_read(business_id)
        if access_error is not None:
            return access_error
        try:
            data = list_workflow_action_audit_events(
                _workflow_ledger(),
                business_id=business_id,
                case_id=_case_scope(),
                limit=_read_limit(),
            )
        except Exception as exc:
            return _handle_projection_errors(business_id, exc)
        return _internal_success(business_id, data)

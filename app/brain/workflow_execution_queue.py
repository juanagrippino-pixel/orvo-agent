"""Safe no-side-effect projection for approved workflow actions.

This module is intentionally a service-layer queue projection. It reads the
workflow action ledger and exposes actions that have cleared approval gates, but
it does not execute case mutations or external side effects. Future executors
must add their own audited execution-attempt ledger before consuming this as a
side-effect source.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.brain.action_catalog import ACTION_CATALOG, is_workflow_approval_required_action
from app.brain.security.redaction import redact_secrets
from app.brain.workflow_action_key_validation import validate_workflow_action_key_filter
from app.brain.workflow_action_ledger import (
    WorkflowActionLedgerError,
    WorkflowActionLedgerRecord,
    WorkflowActionLedgerStore,
    WorkflowApprovalRequest,
)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _approval_requests_by_id(
    requests: list[WorkflowApprovalRequest],
) -> dict[str, WorkflowApprovalRequest]:
    return {request.approval_request_id: request for request in requests}


def _has_matching_approved_request(
    record: WorkflowActionLedgerRecord,
    request: WorkflowApprovalRequest | None,
) -> bool:
    return (
        request is not None
        and record.approval_request_id == request.approval_request_id
        and record.ledger_id == request.ledger_id
        and record.business_id == request.business_id
        and record.case_id == request.case_id
        and record.action_key == request.action_key
        and request.status == "approved"
        and request.decided_at is not None
    )


def _is_pending_execution(
    record: WorkflowActionLedgerRecord,
    request: WorkflowApprovalRequest | None,
) -> bool:
    return (
        is_workflow_approval_required_action(record.action_key)
        and record.approval_state == "approved"
        and record.execution_state == "pending_execution"
        and _has_matching_approved_request(record, request)
    )


def _queue_action_projection(record: WorkflowActionLedgerRecord) -> dict[str, Any]:
    definition = ACTION_CATALOG[record.action_key]
    payload = {
        "ledger_id": record.ledger_id,
        "business_id": record.business_id,
        "case_id": record.case_id,
        "action_key": record.action_key,
        "label": definition.label,
        "mode": definition.mode,
        "side_effect": definition.side_effect,
        "requires_approval": definition.requires_approval,
        "source": record.source,
        "rule_id": record.rule_id,
        "approval_request_id": record.approval_request_id,
        "idempotency_key": record.idempotency_key,
        "actor_ref": record.actor_ref,
        "approval_state": record.approval_state,
        "execution_state": record.execution_state,
        "params": record.params,
        "created_at": _iso(record.created_at),
        "updated_at": _iso(record.updated_at),
        "executor_state": "not_implemented",
        "side_effects_executed": 0,
    }
    redacted = redact_secrets(payload)
    return redacted if isinstance(redacted, dict) else payload


def list_workflow_execution_queue(
    ledger: WorkflowActionLedgerStore,
    *,
    business_id: str,
    case_id: str | None = None,
    action_key: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Project approved actions waiting for a future executor.

    Only records scoped to ``business_id`` and optionally ``case_id`` /
    ``action_key`` with a catalog-defined approval-required action key,
    ``approval_state=approved``, ``execution_state=pending_execution``, and a
    matching approved approval request are returned. The projection is ordered
    deterministically by approval/update time and ledger id, redacted at the
    service boundary, and explicitly declares that execution is disabled with
    zero side effects.
    """

    if case_id is not None and not case_id.strip():
        raise WorkflowActionLedgerError(
            "invalid_workflow_execution_queue_scope",
            "workflow execution queue case_id must be non-empty",
        )
    validate_workflow_action_key_filter(action_key, require_approval_required=True)

    approval_requests = ledger.list_approval_requests(business_id=business_id)
    if action_key is not None:
        approval_requests = [request for request in approval_requests if request.action_key == action_key]
    if case_id is not None:
        approval_requests = [request for request in approval_requests if request.case_id == case_id]
    approval_requests_by_id = _approval_requests_by_id(approval_requests)
    records = ledger.list_actions(business_id=business_id)
    if action_key is not None:
        records = [record for record in records if record.action_key == action_key]
    if case_id is not None:
        records = [record for record in records if record.case_id == case_id]
    records = [
        record
        for record in records
        if _is_pending_execution(record, approval_requests_by_id.get(record.approval_request_id or ""))
    ]
    records.sort(key=lambda record: (record.updated_at, record.ledger_id))
    selected = records if limit is None else records[: max(limit, 0)]
    payload = {
        "business_id": business_id,
        **({"case_id": case_id} if case_id is not None else {}),
        **({"action_key": action_key} if action_key is not None else {}),
        "execution_enabled": False,
        "executor_state": "not_implemented",
        "side_effects_executed": 0,
        "total": len(records),
        "returned": len(selected),
        "actions": [_queue_action_projection(record) for record in selected],
    }
    redacted = redact_secrets(payload)
    return redacted if isinstance(redacted, dict) else payload

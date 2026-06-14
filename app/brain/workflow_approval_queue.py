"""Safe no-side-effect projection for pending workflow approval requests.

This module is intentionally a service-layer queue projection. It reads the
workflow action ledger and exposes approval gates that are still awaiting a
human decision, but it does not approve, reject, execute, mutate cases, dispatch
messages, or call external systems.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.brain.action_catalog import is_workflow_approval_required_action
from app.brain.security.redaction import redact_secrets
from app.brain.workflow_action_key_validation import validate_workflow_action_key_filter
from app.brain.workflow_action_ledger import (
    WorkflowActionLedgerError,
    WorkflowActionLedgerRecord,
    WorkflowActionLedgerStore,
    WorkflowApprovalRequest,
)
from app.brain.workflow_projection_validation import validate_workflow_projection_limit


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _records_by_ledger_id(records: list[WorkflowActionLedgerRecord]) -> dict[str, WorkflowActionLedgerRecord]:
    return {record.ledger_id: record for record in records}


def _is_pending_approval(
    request: WorkflowApprovalRequest,
    record: WorkflowActionLedgerRecord | None,
) -> bool:
    return (
        record is not None
        and request.ledger_id == record.ledger_id
        and request.business_id == record.business_id
        and request.case_id == record.case_id
        and request.action_key == record.action_key
        and request.approval_request_id == record.approval_request_id
        and request.status == "pending"
        and is_workflow_approval_required_action(record.action_key)
        and record.approval_state == "pending"
        and record.execution_state == "blocked_approval_required"
    )


def _approval_request_projection(
    request: WorkflowApprovalRequest,
    record: WorkflowActionLedgerRecord,
) -> dict[str, Any]:
    payload = {
        "approval_request_id": request.approval_request_id,
        "ledger_id": request.ledger_id,
        "business_id": request.business_id,
        "case_id": request.case_id,
        "action_key": request.action_key,
        "requester_ref": request.requester_ref,
        "status": request.status,
        "approval_state": record.approval_state,
        "execution_state": record.execution_state,
        "source": record.source,
        "rule_id": record.rule_id,
        "idempotency_key": record.idempotency_key,
        "params": record.params,
        "requested_at": _iso(request.requested_at),
        "decision_state": "pending_human_approval",
        "approval_execution_enabled": False,
        "side_effects_executed": 0,
    }
    if request.metadata:
        payload["metadata"] = request.metadata
    redacted = redact_secrets(payload)
    return redacted if isinstance(redacted, dict) else payload


def list_workflow_approval_queue(
    ledger: WorkflowActionLedgerStore,
    *,
    business_id: str,
    case_id: str | None = None,
    action_key: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Project pending workflow approval requests for one business.

    Only ledger-backed requests scoped to ``business_id`` and optionally one
    ``case_id`` / ``action_key`` with a catalog-defined approval-required action
    key, ``status=pending``, ``approval_state=pending``, and
    ``execution_state=blocked_approval_required`` are returned. The projection
    is ordered deterministically by request time and approval request id,
    redacted at the service boundary, and explicitly declares that this surface
    performs zero approval/execution side effects.
    """

    if case_id is not None and not case_id.strip():
        raise WorkflowActionLedgerError(
            "invalid_workflow_approval_queue_scope",
            "workflow approval queue case_id must be non-empty",
        )
    parsed_limit = validate_workflow_projection_limit(limit)
    validate_workflow_action_key_filter(action_key, require_approval_required=True)

    records = ledger.list_actions(business_id=business_id)
    if action_key is not None:
        records = [record for record in records if record.action_key == action_key]
    if case_id is not None:
        records = [record for record in records if record.case_id == case_id]
    records_by_id = _records_by_ledger_id(records)
    approval_requests = ledger.list_approval_requests(business_id=business_id)
    if action_key is not None:
        approval_requests = [request for request in approval_requests if request.action_key == action_key]
    if case_id is not None:
        approval_requests = [request for request in approval_requests if request.case_id == case_id]
    pending_pairs = [(request, records_by_id.get(request.ledger_id)) for request in approval_requests]
    pending_pairs = [
        (request, record)
        for request, record in pending_pairs
        if _is_pending_approval(request, record)
    ]
    pending_pairs.sort(key=lambda pair: (pair[0].requested_at, pair[0].approval_request_id))
    selected = pending_pairs if parsed_limit is None else pending_pairs[:parsed_limit]
    payload = {
        "business_id": business_id,
        **({"case_id": case_id} if case_id is not None else {}),
        **({"action_key": action_key} if action_key is not None else {}),
        "approval_execution_enabled": False,
        "decision_state": "pending_human_approval",
        "side_effects_executed": 0,
        "total": len(pending_pairs),
        "returned": len(selected),
        "approval_requests": [
            _approval_request_projection(request, record)
            for request, record in selected
            if record is not None
        ],
    }
    redacted = redact_secrets(payload)
    return redacted if isinstance(redacted, dict) else payload

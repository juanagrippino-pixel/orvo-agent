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

from app.brain.action_catalog import ACTION_CATALOG
from app.brain.security.redaction import redact_secrets
from app.brain.workflow_action_ledger import (
    WorkflowActionLedgerRecord,
    WorkflowActionLedgerStore,
    WorkflowApprovalRequest,
)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _approved_requests_by_id(
    ledger: WorkflowActionLedgerStore,
    *,
    business_id: str,
) -> dict[str, WorkflowApprovalRequest]:
    return {
        request.approval_request_id: request
        for request in ledger.list_approval_requests(business_id=business_id)
        if request.status == "approved"
    }


def _matches_approved_request(
    record: WorkflowActionLedgerRecord,
    request: WorkflowApprovalRequest | None,
) -> bool:
    return (
        request is not None
        and request.approval_request_id == record.approval_request_id
        and request.ledger_id == record.ledger_id
        and request.business_id == record.business_id
        and request.case_id == record.case_id
        and request.action_key == record.action_key
        and request.status == "approved"
    )


def _is_pending_execution(
    record: WorkflowActionLedgerRecord,
    approved_requests_by_id: dict[str, WorkflowApprovalRequest],
) -> bool:
    definition = ACTION_CATALOG.get(record.action_key)
    request = approved_requests_by_id.get(record.approval_request_id or "")
    return (
        definition is not None
        and definition.requires_approval
        and record.approval_state == "approved"
        and record.execution_state == "pending_execution"
        and _matches_approved_request(record, request)
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
    limit: int | None = None,
) -> dict[str, Any]:
    """Project approved actions waiting for a future executor.

    Only records scoped to ``business_id`` with a registered approval-required
    action key, ``approval_state=approved``, ``execution_state=pending_execution``,
    and a matching approved approval request are returned. The projection is
    ordered deterministically by approval/update time and ledger id, redacted at
    the service boundary, and explicitly declares that execution is disabled
    with zero side effects.
    """

    approved_requests = _approved_requests_by_id(ledger, business_id=business_id)
    records = [
        record
        for record in ledger.list_actions(business_id=business_id)
        if _is_pending_execution(record, approved_requests)
    ]
    records.sort(key=lambda record: (record.updated_at, record.ledger_id))
    selected = records if limit is None else records[: max(limit, 0)]
    payload = {
        "business_id": business_id,
        "execution_enabled": False,
        "executor_state": "not_implemented",
        "side_effects_executed": 0,
        "total": len(records),
        "returned": len(selected),
        "actions": [_queue_action_projection(record) for record in selected],
    }
    redacted = redact_secrets(payload)
    return redacted if isinstance(redacted, dict) else payload

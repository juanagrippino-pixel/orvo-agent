"""Safe audit-event projection for workflow action ledger records.

This module is intentionally read-only service-layer plumbing. It projects the
workflow action ledger and approval-request records into deterministic audit
events for operator/internal surfaces, while executing zero side effects and
redacting at the service boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.brain.security.redaction import redact_secrets
from app.brain.workflow_action_ledger import (
    WorkflowActionLedgerError,
    WorkflowActionLedgerRecord,
    WorkflowActionLedgerStore,
    WorkflowApprovalRequest,
)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _records_by_ledger_id(
    records: list[WorkflowActionLedgerRecord],
) -> dict[str, WorkflowActionLedgerRecord]:
    return {record.ledger_id: record for record in records}


def _approval_request_matches_record(
    request: WorkflowApprovalRequest,
    record: WorkflowActionLedgerRecord,
) -> bool:
    return (
        request.approval_request_id == record.approval_request_id
        and request.ledger_id == record.ledger_id
        and request.business_id == record.business_id
        and request.case_id == record.case_id
        and request.action_key == record.action_key
    )


def _redacted_event(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_secrets(payload)
    return redacted if isinstance(redacted, dict) else payload


def _planned_event(record: WorkflowActionLedgerRecord) -> dict[str, Any]:
    return _redacted_event(
        {
            "event_type": "workflow_action_planned",
            "business_id": record.business_id,
            "ledger_id": record.ledger_id,
            "case_id": record.case_id,
            "action_key": record.action_key,
            "source": record.source,
            "actor_ref": record.actor_ref,
            "rule_id": record.rule_id,
            "idempotency_key": record.idempotency_key,
            "approval_request_id": record.approval_request_id,
            "approval_state": record.approval_state,
            "execution_state": record.execution_state,
            "params": record.params,
            "created_at": _iso(record.created_at),
            "side_effects_executed": 0,
        }
    )


def _request_event(
    request: WorkflowApprovalRequest,
    record: WorkflowActionLedgerRecord | None,
) -> dict[str, Any] | None:
    if record is None or not _approval_request_matches_record(request, record):
        return None
    return _redacted_event(
        {
            "event_type": "workflow_approval_requested",
            "business_id": request.business_id,
            "approval_request_id": request.approval_request_id,
            "ledger_id": request.ledger_id,
            "case_id": request.case_id,
            "action_key": request.action_key,
            "requester_ref": request.requester_ref,
            "status": "pending",
            "current_status": request.status,
            "decision_state": "approval_requested",
            "approval_state": "pending",
            "current_approval_state": record.approval_state,
            "execution_state": "blocked_approval_required",
            "current_execution_state": record.execution_state,
            "source": record.source,
            "rule_id": record.rule_id,
            "metadata": request.metadata or {},
            "created_at": _iso(request.requested_at),
            "side_effects_executed": 0,
        }
    )


def _decision_event(
    request: WorkflowApprovalRequest,
    record: WorkflowActionLedgerRecord | None,
) -> dict[str, Any] | None:
    if record is None or request.decided_at is None or not _approval_request_matches_record(request, record):
        return None
    event_type = "workflow_approval_cancelled" if request.status == "cancelled" else "workflow_approval_decided"
    return _redacted_event(
        {
            "event_type": event_type,
            "business_id": request.business_id,
            "approval_request_id": request.approval_request_id,
            "ledger_id": request.ledger_id,
            "case_id": request.case_id,
            "action_key": request.action_key,
            "decision": request.status,
            "decision_actor_ref": request.decision_actor_ref,
            "decision_reason": request.decision_reason,
            "approval_state": record.approval_state,
            "execution_state": record.execution_state,
            "source": record.source,
            "rule_id": record.rule_id,
            "created_at": _iso(request.decided_at),
            "side_effects_executed": 0,
        }
    )


def list_workflow_action_audit_events(
    ledger: WorkflowActionLedgerStore,
    *,
    business_id: str,
    case_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Project workflow action audit events for one business.

    The projection is derived only from canonical ledger/approval records scoped
    by ``business_id`` and optionally by ``case_id``. It emits planning,
    approval-request, and approval-decision events in deterministic timestamp
    order, redacts at the service boundary, and explicitly declares that no
    workflow action or approval side effects were executed by this read path.
    """

    if case_id is not None and not case_id.strip():
        raise WorkflowActionLedgerError("invalid_workflow_audit_scope", "workflow audit case_id must be non-empty")
    if case_id is not None:
        records = [record for record in ledger.list_actions(business_id=business_id) if record.case_id == case_id]
    else:
        records = ledger.list_actions(business_id=business_id)
    records_by_id = _records_by_ledger_id(records)
    events: list[dict[str, Any]] = [_planned_event(record) for record in records]
    approval_requests = ledger.list_approval_requests(business_id=business_id)
    if case_id is not None:
        approval_requests = [request for request in approval_requests if request.case_id == case_id]
    for request in approval_requests:
        record = records_by_id.get(request.ledger_id)
        request_event = _request_event(request, record)
        if request_event is not None:
            events.append(request_event)
        decision_event = _decision_event(request, record)
        if decision_event is not None:
            events.append(decision_event)

    events.sort(
        key=lambda event: (
            str(event.get("created_at", "")),
            str(event.get("ledger_id", "")),
            str(event.get("event_type", "")),
        )
    )
    selected = events if limit is None else events[: max(limit, 0)]
    payload = {
        "business_id": business_id,
        **({"case_id": case_id} if case_id is not None else {}),
        "audit_projection_enabled": True,
        "side_effects_executed": 0,
        "total": len(events),
        "returned": len(selected),
        "events": selected,
    }
    redacted = redact_secrets(payload)
    return redacted if isinstance(redacted, dict) else payload

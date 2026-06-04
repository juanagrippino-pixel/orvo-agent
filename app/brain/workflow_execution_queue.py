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
)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_pending_execution(record: WorkflowActionLedgerRecord) -> bool:
    return (
        record.action_key in ACTION_CATALOG
        and record.approval_state == "approved"
        and record.execution_state == "pending_execution"
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

    Only records scoped to ``business_id`` with a registered action key,
    ``approval_state=approved``, and ``execution_state=pending_execution`` are
    returned. The projection is ordered deterministically by approval/update time
    and ledger id, redacted at the service boundary, and explicitly declares
    that execution is disabled with zero side effects.
    """

    records = [
        record
        for record in ledger.list_actions(business_id=business_id)
        if _is_pending_execution(record)
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

"""Internal operator API projections for Orvo Brain.

This module is transport-agnostic: Flask routes should stay thin and call these
helpers over the canonical stores. The stores remain source of truth.
"""

from __future__ import annotations

from typing import Any, Literal, get_args
from datetime import datetime, timezone

from app.brain.operational_cases import (
    OperationalCase,
    OperationalCaseStatus,
    OperationalCaseStatusError,
    OperationalCaseStore,
)
from app.brain.run_ledger import RunLedger, RunRecord, RunStatus
from app.brain.security.redaction import redact_secrets, redact_text

CaseActionKey = Literal["acknowledge_case", "resolve_case", "add_comment"]
_ALLOWED_CASE_ACTIONS: set[str] = set(get_args(CaseActionKey))
_ALLOWED_CASE_STATUSES: set[str] = set(get_args(OperationalCaseStatus))
_ALLOWED_RUN_STATUSES: set[str] = set(get_args(RunStatus))
_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


class OperatorAPIError(Exception):
    """Safe error intended for API envelopes."""

    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        self.code = code
        self.message = redact_text(message) or "Operator API error"
        self.status_code = status_code
        super().__init__(self.message)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _latest_evidence_at(case: OperationalCase) -> datetime | None:
    if not case.evidence_snapshots:
        return None
    return max(snapshot.captured_at for snapshot in case.evidence_snapshots)


def _source_connectors(case: OperationalCase) -> list[str]:
    return sorted({snapshot.source for snapshot in case.evidence_snapshots if snapshot.source})


def _is_degraded(case: OperationalCase) -> bool:
    return any(snapshot.freshness_state in {"stale", "degraded", "missing"} for snapshot in case.evidence_snapshots)


def parse_limit(value: str | None, *, default: int = _DEFAULT_LIMIT, max_limit: int = _MAX_LIMIT) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise OperatorAPIError("invalid_limit", "limit must be an integer", status_code=400) from exc
    if parsed < 1:
        raise OperatorAPIError("invalid_limit", "limit must be positive", status_code=400)
    return min(parsed, max_limit)


def parse_case_status(value: str | None) -> OperationalCaseStatus | None:
    if value in (None, ""):
        return None
    if value not in _ALLOWED_CASE_STATUSES:
        raise OperatorAPIError("invalid_case_status", f"unsupported case status: {value}", status_code=400)
    return value  # type: ignore[return-value]


def parse_run_status(value: str | None) -> RunStatus | None:
    if value in (None, ""):
        return None
    if value not in _ALLOWED_RUN_STATUSES:
        raise OperatorAPIError("invalid_run_status", f"unsupported run status: {value}", status_code=400)
    return value  # type: ignore[return-value]


def case_queue_item(case: OperationalCase) -> dict[str, Any]:
    return redact_secrets(
        {
            "case_id": case.case_id,
            "business_id": case.business_id,
            "case_type": case.case_type,
            "title": case.title,
            "status": case.status,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "entity_scope": case.entity_scope,
            "opened_at": case.opened_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
            "evidence_count": len(case.evidence_refs),
            "evidence_snapshot_count": len(case.evidence_snapshots),
            "latest_evidence_at": _iso(_latest_evidence_at(case)),
            "source_connectors": _source_connectors(case),
            "degraded": _is_degraded(case),
            "latest_run_id": case.latest_run_id,
        }
    )


def evidence_metric_projection(metric: Any) -> dict[str, Any]:
    return {
        "metric_key": metric.metric_key,
        "label": metric.label,
        "value": metric.value,
        "unit": metric.unit,
        "currency": metric.currency,
        "window": metric.window,
        "observed_at": _iso(metric.observed_at),
        "metadata": metric.metadata,
    }


def evidence_snapshot_projection(snapshot: Any) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_key": snapshot.snapshot_key,
        "captured_at": _iso(snapshot.captured_at),
        "run_id": snapshot.run_id,
        "artifact_ref": snapshot.artifact_ref,
        "evidence_ref": snapshot.evidence_ref,
        "source": snapshot.source,
        "source_label": snapshot.source_label,
        "case_type": snapshot.case_type,
        "entity_scope": snapshot.entity_scope,
        "summary": snapshot.summary,
        "freshness_state": snapshot.freshness_state,
        "metrics": [evidence_metric_projection(metric) for metric in snapshot.metrics],
        "metadata": snapshot.metadata,
    }


def timeline_event_projection(case: OperationalCase, event: Any) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "case_id": event.case_id or case.case_id,
        "event_type": event.event_type,
        "actor_type": event.actor_type,
        "actor_ref": event.actor_ref,
        "run_id": event.run_id,
        "artifact_ref": event.artifact_ref,
        "created_at": _iso(event.created_at),
        "summary": event.summary,
        "evidence_snapshot_ids": event.evidence_snapshot_ids,
        "metadata": event.metadata,
    }


def case_detail(case: OperationalCase) -> dict[str, Any]:
    return redact_secrets(
        {
            "case_id": case.case_id,
            "business_id": case.business_id,
            "case_type": case.case_type,
            "dedupe_key": case.dedupe_key,
            "title": case.title,
            "status": case.status,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "entity_scope": case.entity_scope,
            "opened_at": _iso(case.opened_at),
            "updated_at": _iso(case.updated_at),
            "acknowledged_at": _iso(case.acknowledged_at),
            "resolved_at": _iso(case.resolved_at),
            "latest_run_id": case.latest_run_id,
            "source_run_ids": case.source_run_ids,
            "evidence_refs": case.evidence_refs,
            "artifact_refs": case.artifact_refs,
            "evidence_snapshot_count": len(case.evidence_snapshots),
            "evidence_snapshots": [evidence_snapshot_projection(snapshot) for snapshot in case.evidence_snapshots],
            "timeline": [timeline_event_projection(case, event) for event in case.timeline],
            "metadata": case.metadata,
        }
    )


def run_history_item(run: RunRecord) -> dict[str, Any]:
    return redact_secrets(
        {
            "run_id": run.run_id,
            "business_id": run.business_id,
            "trigger_type": run.trigger_type,
            "status": run.status,
            "started_at": run.started_at.isoformat(),
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "connector_count": len(run.connector_outcomes),
            "artifact_count": len(run.artifacts),
            "dispatch_count": len(run.dispatch_outcomes),
            "cases_opened": run.summary_metadata.get("cases_opened", 0),
            "cases_updated": run.summary_metadata.get("cases_updated", 0),
            "summary_metadata": run.summary_metadata,
        }
    )


def run_detail(run: RunRecord) -> dict[str, Any]:
    return redact_secrets(run.model_dump(mode="json"))


def list_case_queue(
    store: OperationalCaseStore,
    *,
    business_id: str,
    status: str | None,
    limit: str | None,
    jql: str | None = None,
) -> dict[str, Any]:
    if jql not in (None, ""):
        if status not in (None, ""):
            raise OperatorAPIError("conflicting_case_filters", "status and jql filters are mutually exclusive", status_code=400)
        from app.brain.operator_views import query_case_queue

        return query_case_queue(store, business_id=business_id, jql=jql, limit=limit)

    parsed_status = parse_case_status(status)
    parsed_limit = parse_limit(limit)
    cases = store.list_cases(business_id=business_id, status=parsed_status, limit=parsed_limit)
    return {"cases": [case_queue_item(case) for case in cases], "limit": parsed_limit}


def get_scoped_case(store: OperationalCaseStore, *, business_id: str, case_id: str) -> OperationalCase:
    case = store.get_case(case_id)
    if case is None or case.business_id != business_id:
        raise OperatorAPIError("case_not_found", "case not found", status_code=404)
    return case


def get_case_projection(store: OperationalCaseStore, *, business_id: str, case_id: str) -> dict[str, Any]:
    return {"case": case_detail(get_scoped_case(store, business_id=business_id, case_id=case_id))}


def list_builtin_case_views() -> dict[str, Any]:
    from app.brain.operator_views import builtin_case_views

    return {"views": builtin_case_views()}


def execute_builtin_case_view(
    store: OperationalCaseStore,
    *,
    business_id: str,
    view_id: str,
    limit: str | None,
) -> dict[str, Any]:
    from app.brain.operator_views import get_builtin_case_view, query_case_queue

    view = get_builtin_case_view(view_id)
    return query_case_queue(store, business_id=business_id, jql=view["jql"], limit=limit, view=view)


def apply_case_action(
    store: OperationalCaseStore,
    *,
    business_id: str,
    case_id: str,
    action_key: str,
    actor_ref: str | None = None,
    actor: str | None = None,
    reason: str | None = None,
    comment: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if action_key not in _ALLOWED_CASE_ACTIONS:
        raise OperatorAPIError("unknown_action_key", f"unknown action_key: {action_key}", status_code=400)
    effective_actor_ref = actor_ref if actor_ref is not None else actor
    if not effective_actor_ref:
        raise OperatorAPIError("missing_operator_actor", "operator actor is required", status_code=400)

    case = get_scoped_case(store, business_id=business_id, case_id=case_id)
    if action_key == "add_comment":
        if not isinstance(comment, str) or not comment.strip():
            raise OperatorAPIError("invalid_comment", "comment must be a non-empty string", status_code=400)
        updated = store.add_comment(
            case.case_id,
            actor_type="operator",
            actor_ref=effective_actor_ref,
            comment=comment.strip(),
            metadata=metadata,
        )
        return {"case": case_detail(updated)}

    target_status: OperationalCaseStatus = "acknowledged" if action_key == "acknowledge_case" else "resolved"
    default_reason = "Acknowledged by operator." if action_key == "acknowledge_case" else "Resolved by operator."
    try:
        updated = store.transition_case(
            case.case_id,
            status=target_status,
            actor_type="operator",
            actor_ref=effective_actor_ref,
            reason=reason or default_reason,
        )
    except OperationalCaseStatusError as exc:
        raise OperatorAPIError("invalid_case_transition", str(exc), status_code=409) from exc
    return {"case": case_detail(updated)}


def list_run_history(ledger: RunLedger, *, business_id: str, status: str | None, limit: str | None) -> dict[str, Any]:
    parsed_status = parse_run_status(status)
    parsed_limit = parse_limit(limit)
    runs = ledger.list_runs(business_id=business_id, status=parsed_status, limit=parsed_limit)
    return {"runs": [run_history_item(run) for run in runs], "limit": parsed_limit}


def get_scoped_run(ledger: RunLedger, *, business_id: str, run_id: str) -> RunRecord:
    run = ledger.get_run(run_id)
    if run is None or run.business_id != business_id:
        raise OperatorAPIError("run_not_found", "run not found", status_code=404)
    return run


def get_run_projection(ledger: RunLedger, *, business_id: str, run_id: str) -> dict[str, Any]:
    return {"run": run_detail(get_scoped_run(ledger, business_id=business_id, run_id=run_id))}

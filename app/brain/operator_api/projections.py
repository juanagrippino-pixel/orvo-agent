from __future__ import annotations

from app.brain.action_catalog import ACTION_CATALOG
from app.brain.run_ledger import redact_metadata
from app.brain.work_items import case_work_item_projection

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403


def case_queue_item(case: OperationalCase) -> dict[str, Any]:
    work_item = case_work_item_projection(case)
    return redact_secrets(
        {
            "case_id": case.case_id,
            "business_id": case.business_id,
            "case_type": case.case_type,
            "title": case.title,
            "status": case.status,
            "status_category": work_item["status_category"],
            "project_key": work_item["project_key"],
            "issue_type": work_item["issue_type"],
            "release_state": work_item["release_state"],
            "work_item_id": work_item["work_item_id"],
            "work_item": work_item,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "entity_scope": case.entity_scope,
            "opened_at": case.opened_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
            "acknowledged_at": _iso(case.acknowledged_at),
            "assigned_at": _iso(case.assigned_at),
            "assignee_ref": case.assignee_ref,
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


def _case_suggested_action_keys(case: OperationalCase) -> list[str]:
    raw_keys = case.metadata.get("suggested_action_keys")
    if not isinstance(raw_keys, list):
        return []
    keys: list[str] = []
    for raw_key in raw_keys:
        if not isinstance(raw_key, str):
            continue
        definition = ACTION_CATALOG.get(raw_key)
        if definition is None or case.case_type not in definition.case_families:
            continue
        if raw_key not in keys:
            keys.append(raw_key)
    return keys


def _case_suggested_actions(case: OperationalCase) -> list[dict[str, Any]]:
    return [
        ACTION_CATALOG[action_key].operator_projection(can_execute_case_actions=False)
        for action_key in _case_suggested_action_keys(case)
    ]

def case_detail(case: OperationalCase) -> dict[str, Any]:
    work_item = case_work_item_projection(case)
    return redact_secrets(
        {
            "case_id": case.case_id,
            "business_id": case.business_id,
            "case_type": case.case_type,
            "dedupe_key": case.dedupe_key,
            "title": case.title,
            "status": case.status,
            "status_category": work_item["status_category"],
            "project_key": work_item["project_key"],
            "issue_type": work_item["issue_type"],
            "release_state": work_item["release_state"],
            "work_item_id": work_item["work_item_id"],
            "work_item": work_item,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "entity_scope": case.entity_scope,
            "opened_at": _iso(case.opened_at),
            "updated_at": _iso(case.updated_at),
            "acknowledged_at": _iso(case.acknowledged_at),
            "assigned_at": _iso(case.assigned_at),
            "assignee_ref": case.assignee_ref,
            "resolved_at": _iso(case.resolved_at),
            "dismissed_at": _iso(case.dismissed_at),
            "latest_run_id": case.latest_run_id,
            "source_run_ids": case.source_run_ids,
            "evidence_refs": case.evidence_refs,
            "artifact_refs": case.artifact_refs,
            "evidence_snapshot_count": len(case.evidence_snapshots),
            "evidence_snapshots": [evidence_snapshot_projection(snapshot) for snapshot in case.evidence_snapshots],
            "timeline": [timeline_event_projection(case, event) for event in case.timeline],
            "suggested_action_keys": _case_suggested_action_keys(case),
            "suggested_actions": _case_suggested_actions(case),
            "metadata": case.metadata,
        }
    )

def _redact_run_projection(value: Any) -> Any:
    """Redact run-ledger data again at the operator API boundary.

    Run ledger stores normally validate and redact records on write/read, but
    internal API projections should also be defensive for legacy rows or custom
    ledger implementations. In particular, compiled-runtime ``secret_refs`` URI
    values are useful inside runtime metadata but must not cross operator API
    boundaries.
    """

    return redact_metadata(value)


def _latest_dispatch_outcome(run: RunRecord) -> Any | None:
    if not run.dispatch_outcomes:
        return None
    return max(run.dispatch_outcomes, key=lambda outcome: (outcome.created_at, outcome.attempt_number))


def _dispatch_message_type(outcome: Any) -> str:
    raw_value = outcome.metadata.get("message_type") if isinstance(outcome.metadata, dict) else None
    if not isinstance(raw_value, str) or not raw_value.strip():
        return "unknown"
    candidate = raw_value.strip()
    redacted = redact_text(candidate) or "[REDACTED]"
    return candidate if redacted == candidate else "unknown"


def _dispatch_summary_item(outcome: Any) -> dict[str, Any]:
    return {
        "channel": outcome.channel,
        "status": outcome.status,
        "message_type": _dispatch_message_type(outcome),
        "attempt_number": outcome.attempt_number,
        "message_id": outcome.message_id,
        "created_at": outcome.created_at.isoformat(),
    }


def _latest_dispatch_by_message_type(run: RunRecord, message_type: str) -> Any | None:
    matching = [outcome for outcome in run.dispatch_outcomes if _dispatch_message_type(outcome) == message_type]
    if not matching:
        return None
    return max(matching, key=lambda outcome: (outcome.created_at, outcome.attempt_number))


def dispatch_summary(run: RunRecord) -> dict[str, Any]:
    """Return a redacted operator projection over run dispatch outcomes.

    The summary is deliberately derived from immutable run-ledger dispatch
    outcomes. It helps operators distinguish the primary daily report from
    secondary owner-case-brief delivery without treating channel text or API
    output as workflow state.
    """

    by_status = {status: 0 for status in sorted({outcome.status for outcome in run.dispatch_outcomes})}
    by_message_type = {
        message_type: 0 for message_type in sorted({_dispatch_message_type(outcome) for outcome in run.dispatch_outcomes})
    }
    for outcome in run.dispatch_outcomes:
        by_status[outcome.status] = by_status.get(outcome.status, 0) + 1
        message_type = _dispatch_message_type(outcome)
        by_message_type[message_type] = by_message_type.get(message_type, 0) + 1

    latest = _latest_dispatch_outcome(run)
    primary_daily_report = _latest_dispatch_by_message_type(run, "daily_report")
    owner_case_brief = _latest_dispatch_by_message_type(run, "owner_case_brief")
    return _redact_run_projection(
        {
            "total": len(run.dispatch_outcomes),
            "by_status": by_status,
            "by_message_type": by_message_type,
            "latest": _dispatch_summary_item(latest) if latest is not None else None,
            "primary_daily_report": _dispatch_summary_item(primary_daily_report)
            if primary_daily_report is not None
            else None,
            "owner_case_brief": _dispatch_summary_item(owner_case_brief) if owner_case_brief is not None else None,
        }
    )


def run_history_item(run: RunRecord) -> dict[str, Any]:
    latest_dispatch = _latest_dispatch_outcome(run)
    return _redact_run_projection(
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
            "dispatch_status": latest_dispatch.status if latest_dispatch is not None else None,
            "latest_dispatch_channel": latest_dispatch.channel if latest_dispatch is not None else None,
            "dispatch_summary": dispatch_summary(run),
            "cases_opened": run.summary_metadata.get("cases_opened", 0),
            "cases_updated": run.summary_metadata.get("cases_updated", 0),
            "summary_metadata": run.summary_metadata,
        }
    )


def run_detail(run: RunRecord) -> dict[str, Any]:
    projection = run.model_dump(mode="json")
    projection["dispatch_summary"] = dispatch_summary(run)
    return _redact_run_projection(projection)

__all__ = [name for name in globals() if not name.startswith("__")]

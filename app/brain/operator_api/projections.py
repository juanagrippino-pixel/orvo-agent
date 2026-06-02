from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403


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

__all__ = [name for name in globals() if not name.startswith("__")]

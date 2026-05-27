"""Internal operator API projections for Orvo Brain.

This module is transport-agnostic: Flask routes should stay thin and call these
helpers over the canonical stores. The stores remain source of truth.
"""

from __future__ import annotations

from typing import Any, Literal, get_args
from datetime import datetime, timezone

from app.brain.operational_cases import (
    ActorType,
    OperationalCase,
    OperationalCaseStatus,
    OperationalCaseStatusError,
    OperationalCaseStore,
    TimelineEventType,
)
from app.brain.run_ledger import RunLedger, RunRecord, RunStatus
from app.brain.security.redaction import redact_secrets, redact_text

CaseActionKey = Literal["acknowledge_case", "resolve_case", "add_comment"]
_ALLOWED_CASE_ACTIONS: set[str] = set(get_args(CaseActionKey))
_ALLOWED_CASE_STATUSES: set[str] = set(get_args(OperationalCaseStatus))
_ALLOWED_RUN_STATUSES: set[str] = set(get_args(RunStatus))
_ALLOWED_TIMELINE_EVENT_TYPES: set[str] = set(get_args(TimelineEventType))
_ALLOWED_TIMELINE_ACTOR_TYPES: set[str] = set(get_args(ActorType))
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


def parse_timeline_event_type(value: str | None) -> TimelineEventType | None:
    if value in (None, ""):
        return None
    if value not in _ALLOWED_TIMELINE_EVENT_TYPES:
        raise OperatorAPIError(
            "invalid_timeline_event_type",
            f"unsupported timeline event_type: {value}",
            status_code=400,
        )
    return value  # type: ignore[return-value]


def parse_timeline_actor_type(value: str | None) -> ActorType | None:
    if value in (None, ""):
        return None
    if value not in _ALLOWED_TIMELINE_ACTOR_TYPES:
        raise OperatorAPIError(
            "invalid_timeline_actor_type",
            f"unsupported timeline actor_type: {value}",
            status_code=400,
        )
    return value  # type: ignore[return-value]


def parse_run_status(value: str | None) -> RunStatus | None:
    if value in (None, ""):
        return None
    if value not in _ALLOWED_RUN_STATUSES:
        raise OperatorAPIError("invalid_run_status", f"unsupported run status: {value}", status_code=400)
    return value  # type: ignore[return-value]


def normalize_operator_actor(actor_ref: Any, actor: Any) -> str:
    effective_actor_ref = actor_ref if actor_ref is not None else actor
    if effective_actor_ref is None:
        raise OperatorAPIError("missing_operator_actor", "operator actor is required", status_code=400)
    if not isinstance(effective_actor_ref, str):
        raise OperatorAPIError("invalid_operator_actor", "operator actor must be a string", status_code=400)
    normalized = effective_actor_ref.strip()
    if not normalized:
        raise OperatorAPIError("missing_operator_actor", "operator actor is required", status_code=400)
    return normalized


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


def list_case_timeline(
    store: OperationalCaseStore,
    *,
    business_id: str,
    case_id: str,
    event_type: str | None = None,
    actor_type: str | None = None,
    limit: str | None = None,
) -> dict[str, Any]:
    parsed_event_type = parse_timeline_event_type(event_type)
    parsed_actor_type = parse_timeline_actor_type(actor_type)
    parsed_limit = parse_limit(limit)
    case = get_scoped_case(store, business_id=business_id, case_id=case_id)
    events = list(case.timeline)
    if parsed_event_type is not None:
        events = [event for event in events if event.event_type == parsed_event_type]
    if parsed_actor_type is not None:
        events = [event for event in events if event.actor_type == parsed_actor_type]
    total = len(events)
    limited = events[-parsed_limit:] if total > parsed_limit else events
    return redact_secrets(
        {
            "case_id": case.case_id,
            "case_status": case.status,
            "filters": {
                "event_type": parsed_event_type,
                "actor_type": parsed_actor_type,
            },
            "events": [timeline_event_projection(case, event) for event in limited],
            "limit": parsed_limit,
            "count": len(limited),
            "total": total,
        }
    )


_ACTIONABLE_STATUSES: frozenset[OperationalCaseStatus] = frozenset({"open", "acknowledged"})


def summarize_case_queue(store: OperationalCaseStore, *, business_id: str) -> dict[str, Any]:
    """Deterministic counts over the case queue for a single business.

    Scoped projection: never returns cases from other tenants and never reads
    raw payloads beyond what the case store already exposes. Counts cover the
    full lifecycle (open/acknowledged/resolved); actionable totals isolate the
    in-flight slice that operator surfaces typically lead with.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_case_type: dict[str, int] = {}
    actionable_by_severity: dict[str, int] = {}
    actionable_total = 0
    actionable_degraded = 0
    for case in cases:
        by_status[case.status] = by_status.get(case.status, 0) + 1
        by_severity[case.severity] = by_severity.get(case.severity, 0) + 1
        by_case_type[case.case_type] = by_case_type.get(case.case_type, 0) + 1
        if case.status in _ACTIONABLE_STATUSES:
            actionable_total += 1
            actionable_by_severity[case.severity] = actionable_by_severity.get(case.severity, 0) + 1
            if _is_degraded(case):
                actionable_degraded += 1
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "by_status": by_status,
            "by_severity": by_severity,
            "by_case_type": by_case_type,
            "actionable_total": actionable_total,
            "actionable_by_severity": actionable_by_severity,
            "actionable_degraded": actionable_degraded,
        }
    )


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


_AGE_BUCKETS: tuple[tuple[str, int | None], ...] = (
    ("under_1h", 3600),
    ("under_6h", 21600),
    ("under_24h", 86400),
    ("under_7d", 604800),
    ("over_7d", None),
)


def _classify_age_bucket(age_seconds: int) -> str:
    for name, upper in _AGE_BUCKETS:
        if upper is None or age_seconds < upper:
            return name
    return _AGE_BUCKETS[-1][0]


def summarize_case_queue_aging(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Deterministic age histogram for actionable cases in a business.

    Buckets actionable (open + acknowledged) cases by ``now - opened_at`` so
    operator surfaces can see how stale the in-flight workload is. Strictly
    scoped per tenant; ``now`` is injectable for deterministic tests and
    defaults to current UTC.
    """

    if now is None:
        reference = _now_utc()
    else:
        if now.tzinfo is None or now.utcoffset() is None:
            raise OperatorAPIError("invalid_now", "now must be timezone-aware", status_code=400)
        reference = now.astimezone(timezone.utc)

    buckets: dict[str, int] = {name: 0 for name, _ in _AGE_BUCKETS}
    severity_by_bucket: dict[str, dict[str, int]] = {name: {} for name, _ in _AGE_BUCKETS}
    actionable_total = 0
    oldest_age = -1
    oldest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        actionable_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(age_seconds)
        buckets[bucket] += 1
        severity_counts = severity_by_bucket[bucket]
        severity_counts[case.severity] = severity_counts.get(case.severity, 0) + 1
        if age_seconds > oldest_age:
            oldest_age = age_seconds
            oldest_case = case
    oldest_payload: dict[str, Any] | None = None
    if oldest_case is not None:
        oldest_payload = {
            "case_id": oldest_case.case_id,
            "case_type": oldest_case.case_type,
            "status": oldest_case.status,
            "severity": oldest_case.severity,
            "opened_at": oldest_case.opened_at.isoformat(),
            "age_seconds": oldest_age,
        }
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": actionable_total,
            "by_age_bucket": buckets,
            "by_age_bucket_severity": severity_by_bucket,
            "oldest_actionable": oldest_payload,
        }
    )


def summarize_case_queue_aging_by_case_type(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Case-type-split age histogram for actionable cases in a business.

    Mirrors :func:`summarize_case_queue_aging` but groups each age bucket by
    case type instead of severity, so operator surfaces can see which case
    families dominate the in-flight backlog at every age horizon. Strictly
    scoped per tenant; ``now`` is injectable for deterministic tests and
    defaults to current UTC.
    """

    if now is None:
        reference = _now_utc()
    else:
        if now.tzinfo is None or now.utcoffset() is None:
            raise OperatorAPIError("invalid_now", "now must be timezone-aware", status_code=400)
        reference = now.astimezone(timezone.utc)

    buckets: dict[str, int] = {name: 0 for name, _ in _AGE_BUCKETS}
    case_type_by_bucket: dict[str, dict[str, int]] = {name: {} for name, _ in _AGE_BUCKETS}
    actionable_total = 0
    oldest_age = -1
    oldest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        actionable_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(age_seconds)
        buckets[bucket] += 1
        case_type_counts = case_type_by_bucket[bucket]
        case_type_counts[case.case_type] = case_type_counts.get(case.case_type, 0) + 1
        if age_seconds > oldest_age:
            oldest_age = age_seconds
            oldest_case = case
    oldest_payload: dict[str, Any] | None = None
    if oldest_case is not None:
        oldest_payload = {
            "case_id": oldest_case.case_id,
            "case_type": oldest_case.case_type,
            "status": oldest_case.status,
            "severity": oldest_case.severity,
            "opened_at": oldest_case.opened_at.isoformat(),
            "age_seconds": oldest_age,
        }
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": actionable_total,
            "by_age_bucket": buckets,
            "by_age_bucket_case_type": case_type_by_bucket,
            "oldest_actionable": oldest_payload,
        }
    )


def list_top_actionable_cases_by_age(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Top-N oldest actionable cases for a business, ordered oldest first.

    Complements :func:`summarize_case_queue_aging`, which only exposes a single
    ``oldest_actionable`` case. Operator triage surfaces use this list to pick
    the next handful of cases to work, scoped strictly per tenant. Ties on age
    are broken by ``case_id`` ASC for deterministic ordering. ``now`` is
    injectable for tests and defaults to current UTC.
    """

    if now is None:
        reference = _now_utc()
    else:
        if now.tzinfo is None or now.utcoffset() is None:
            raise OperatorAPIError("invalid_now", "now must be timezone-aware", status_code=400)
        reference = now.astimezone(timezone.utc)

    parsed_limit = parse_limit(limit)
    actionable: list[tuple[int, str, OperationalCase]] = []
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        opened_at = case.opened_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        actionable.append((age_seconds, case.case_id, case))

    # Oldest first (age DESC); tie-break by case_id ASC for deterministic order.
    actionable.sort(key=lambda item: (-item[0], item[1]))
    limited = actionable[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "status": case.status,
            "severity": case.severity,
            "opened_at": case.opened_at.isoformat(),
            "age_seconds": age_seconds,
        }
        for age_seconds, _case_id, case in limited
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": len(actionable),
            "cases": cases_payload,
            "limit": parsed_limit,
            "count": len(cases_payload),
        }
    )


def list_top_actionable_cases_by_priority(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Top-N highest-priority actionable cases for a business.

    Counterpart to :func:`list_top_actionable_cases_by_age`: operators triage
    by priority as often as by age, so this projection ranks open and
    acknowledged cases by ``priority_score`` DESC. Ties on priority are broken
    by ``case_id`` ASC for deterministic ordering. ``age_seconds`` is included
    on each row for context but does not influence ordering. ``now`` is
    injectable for tests and defaults to current UTC. Strictly scoped per
    tenant.
    """

    if now is None:
        reference = _now_utc()
    else:
        if now.tzinfo is None or now.utcoffset() is None:
            raise OperatorAPIError("invalid_now", "now must be timezone-aware", status_code=400)
        reference = now.astimezone(timezone.utc)

    parsed_limit = parse_limit(limit)
    actionable: list[tuple[int, str, int, OperationalCase]] = []
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        opened_at = case.opened_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        actionable.append((case.priority_score, case.case_id, age_seconds, case))

    # Highest priority first; tie-break by case_id ASC for deterministic order.
    actionable.sort(key=lambda item: (-item[0], item[1]))
    limited = actionable[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "status": case.status,
            "severity": case.severity,
            "priority_score": priority_score,
            "opened_at": case.opened_at.isoformat(),
            "age_seconds": age_seconds,
        }
        for priority_score, _case_id, age_seconds, case in limited
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": len(actionable),
            "cases": cases_payload,
            "limit": parsed_limit,
            "count": len(cases_payload),
        }
    )


def list_top_stalled_actionable_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Top-N most-stalled actionable cases for a business, ordered by idleness.

    Complements :func:`list_top_actionable_cases_by_age`, which orders by
    ``now - opened_at`` and so always promotes long-lived cases regardless of
    recent activity. This projection orders by ``now - updated_at`` so that an
    old case that was recently acknowledged or commented on ranks below a
    younger case that has not moved at all. Ties on idleness are broken by
    ``case_id`` ASC for deterministic ordering. ``age_seconds`` is included on
    each row for context but does not influence ordering. ``now`` is injectable
    for tests and defaults to current UTC. Strictly scoped per tenant.
    """

    if now is None:
        reference = _now_utc()
    else:
        if now.tzinfo is None or now.utcoffset() is None:
            raise OperatorAPIError("invalid_now", "now must be timezone-aware", status_code=400)
        reference = now.astimezone(timezone.utc)

    parsed_limit = parse_limit(limit)
    actionable: list[tuple[int, str, int, OperationalCase]] = []
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        opened_at = case.opened_at.astimezone(timezone.utc)
        updated_at = case.updated_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        idle_seconds = max(int((reference - updated_at).total_seconds()), 0)
        actionable.append((idle_seconds, case.case_id, age_seconds, case))

    # Most stalled first (idle DESC); tie-break by case_id ASC for deterministic order.
    actionable.sort(key=lambda item: (-item[0], item[1]))
    limited = actionable[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "status": case.status,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "opened_at": case.opened_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
            "age_seconds": age_seconds,
            "idle_seconds": idle_seconds,
        }
        for idle_seconds, _case_id, age_seconds, case in limited
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": len(actionable),
            "cases": cases_payload,
            "limit": parsed_limit,
            "count": len(cases_payload),
        }
    )


_FRESHNESS_RANK: dict[str, int] = {
    "fresh": 0,
    "unknown": 1,
    "stale": 2,
    "degraded": 3,
    "missing": 4,
}


def _worst_freshness_state(case: OperationalCase) -> str | None:
    worst: str | None = None
    worst_rank = -1
    for snapshot in case.evidence_snapshots:
        rank = _FRESHNESS_RANK.get(snapshot.freshness_state, -1)
        if rank > worst_rank:
            worst_rank = rank
            worst = snapshot.freshness_state
    return worst


def list_top_actionable_degraded_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Top-N actionable cases whose evidence snapshots are not fresh.

    Drills into the ``actionable_degraded`` counter exposed by
    :func:`summarize_case_queue`: surfaces which urgent cases are stuck on
    stale, degraded, or missing evidence so operators know which connector to
    re-run. Ordered by ``priority_score`` DESC with ``case_id`` ASC as a
    deterministic tie-breaker. Each row includes the worst freshness state,
    latest evidence capture time, and contributing source connectors so the
    operator surface can render triage hints without extra lookups. ``now`` is
    injectable for tests and defaults to current UTC. Strictly scoped per
    tenant.
    """

    if now is None:
        reference = _now_utc()
    else:
        if now.tzinfo is None or now.utcoffset() is None:
            raise OperatorAPIError("invalid_now", "now must be timezone-aware", status_code=400)
        reference = now.astimezone(timezone.utc)

    parsed_limit = parse_limit(limit)
    degraded: list[tuple[int, str, int, OperationalCase]] = []
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        if not _is_degraded(case):
            continue
        opened_at = case.opened_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        degraded.append((case.priority_score, case.case_id, age_seconds, case))

    # Highest priority first; tie-break by case_id ASC for deterministic order.
    degraded.sort(key=lambda item: (-item[0], item[1]))
    limited = degraded[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "status": case.status,
            "severity": case.severity,
            "priority_score": priority_score,
            "opened_at": case.opened_at.isoformat(),
            "age_seconds": age_seconds,
            "freshness_state": _worst_freshness_state(case),
            "latest_evidence_at": _iso(_latest_evidence_at(case)),
            "source_connectors": _source_connectors(case),
        }
        for priority_score, _case_id, age_seconds, case in limited
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_degraded_total": len(degraded),
            "cases": cases_payload,
            "limit": parsed_limit,
            "count": len(cases_payload),
        }
    )


def list_recently_resolved_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
) -> dict[str, Any]:
    """Top-N most-recently-resolved cases for a business.

    Complements the actionable projections (`list_top_actionable_cases_by_age`
    and friends) by surfacing the closed-flow side: operator surfaces use this
    for "Recently closed" panels and post-mortem hand-offs. Ordered by
    ``resolved_at`` DESC with ``case_id`` ASC as a deterministic tie-breaker.
    Each row includes ``resolution_seconds`` (opened_at -> resolved_at) so the
    surface can render time-to-resolve without extra lookups. Strictly scoped
    per tenant; the projection reads ``resolved_at`` directly from the case
    store, so it needs no ``now`` parameter.
    """

    parsed_limit = parse_limit(limit)
    resolved: list[tuple[datetime, str, OperationalCase]] = []
    for case in store.list_cases(business_id=business_id, status="resolved", limit=None):
        if case.resolved_at is None:
            continue
        resolved.append((case.resolved_at.astimezone(timezone.utc), case.case_id, case))

    # Most recently resolved first; tie-break by case_id ASC for deterministic order.
    resolved.sort(key=lambda item: (-item[0].timestamp(), item[1]))
    limited = resolved[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "status": case.status,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "opened_at": case.opened_at.isoformat(),
            "resolved_at": case.resolved_at.isoformat(),
            "resolution_seconds": int((case.resolved_at - case.opened_at).total_seconds()),
        }
        for _resolved_at, _case_id, case in limited
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "resolved_total": len(resolved),
            "cases": cases_payload,
            "limit": parsed_limit,
            "count": len(cases_payload),
        }
    )


def list_recently_opened_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
) -> dict[str, Any]:
    """Top-N most-recently-opened cases that have not yet been acknowledged.

    Symmetric to :func:`list_recently_acknowledged_cases` and
    :func:`list_recently_resolved_cases`: surfaces the inflow side of the
    workflow so operator surfaces can render a "Just landed" panel and pick up
    fresh work before it goes stale. Only cases currently in ``open`` status
    are included; once acknowledged they belong to the recently-acknowledged
    projection. Ordered by ``opened_at`` DESC with ``case_id`` ASC as a
    deterministic tie-breaker. Strictly scoped per tenant; the projection
    reads ``opened_at`` directly from the case store, so it needs no ``now``
    parameter.
    """

    parsed_limit = parse_limit(limit)
    opened: list[tuple[datetime, str, OperationalCase]] = []
    for case in store.list_cases(business_id=business_id, status="open", limit=None):
        opened.append((case.opened_at.astimezone(timezone.utc), case.case_id, case))

    # Most recently opened first; tie-break by case_id ASC for deterministic order.
    opened.sort(key=lambda item: (-item[0].timestamp(), item[1]))
    limited = opened[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "status": case.status,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "opened_at": case.opened_at.isoformat(),
        }
        for _opened_at, _case_id, case in limited
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "open_total": len(opened),
            "cases": cases_payload,
            "limit": parsed_limit,
            "count": len(cases_payload),
        }
    )


def list_recently_acknowledged_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
) -> dict[str, Any]:
    """Top-N most-recently-acknowledged cases that are still in flight.

    Symmetric to :func:`list_recently_resolved_cases`: surfaces the ack side of
    the workflow so operator surfaces can render a "Just picked up" panel and
    confirm ownership churn. Only cases currently in ``acknowledged`` status are
    included; resolved cases have moved on and are owned by the recently-resolved
    projection. Ordered by ``acknowledged_at`` DESC with ``case_id`` ASC as a
    deterministic tie-breaker. Each row includes ``acknowledgment_seconds``
    (opened_at -> acknowledged_at) so the surface can render time-to-acknowledge
    without extra lookups. Strictly scoped per tenant; the projection reads
    ``acknowledged_at`` directly from the case store, so it needs no ``now``
    parameter.
    """

    parsed_limit = parse_limit(limit)
    acknowledged: list[tuple[datetime, str, OperationalCase]] = []
    for case in store.list_cases(business_id=business_id, status="acknowledged", limit=None):
        if case.acknowledged_at is None:
            continue
        acknowledged.append((case.acknowledged_at.astimezone(timezone.utc), case.case_id, case))

    # Most recently acknowledged first; tie-break by case_id ASC for deterministic order.
    acknowledged.sort(key=lambda item: (-item[0].timestamp(), item[1]))
    limited = acknowledged[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "status": case.status,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "opened_at": case.opened_at.isoformat(),
            "acknowledged_at": case.acknowledged_at.isoformat(),
            "acknowledgment_seconds": int((case.acknowledged_at - case.opened_at).total_seconds()),
        }
        for _acknowledged_at, _case_id, case in limited
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "acknowledged_total": len(acknowledged),
            "cases": cases_payload,
            "limit": parsed_limit,
            "count": len(cases_payload),
        }
    )


def _latency_summary(seconds: list[int]) -> dict[str, int]:
    if not seconds:
        return {}
    sorted_seconds = sorted(seconds)
    count = len(sorted_seconds)
    midpoint = count // 2
    if count % 2 == 1:
        median = sorted_seconds[midpoint]
    else:
        median = (sorted_seconds[midpoint - 1] + sorted_seconds[midpoint]) // 2
    return {
        "min": sorted_seconds[0],
        "max": sorted_seconds[-1],
        "avg": sum(sorted_seconds) // count,
        "median": median,
    }


def summarize_case_workflow_throughput(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Deterministic lifecycle latency aggregates for cases in a business.

    Computes time-to-acknowledge (opened_at -> acknowledged_at) and
    time-to-resolve (opened_at -> resolved_at) in whole seconds for cases
    that have reached those lifecycle states. Open-only cases contribute to
    ``total`` but not to the latency aggregates. Strictly scoped per tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    ack_latencies: list[int] = []
    resolve_latencies: list[int] = []
    for case in cases:
        if case.acknowledged_at is not None:
            ack_latencies.append(int((case.acknowledged_at - case.opened_at).total_seconds()))
        if case.resolved_at is not None:
            resolve_latencies.append(int((case.resolved_at - case.opened_at).total_seconds()))
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "acknowledged_count": len(ack_latencies),
            "resolved_count": len(resolve_latencies),
            "time_to_acknowledge_seconds": _latency_summary(ack_latencies),
            "time_to_resolve_seconds": _latency_summary(resolve_latencies),
        }
    )


def summarize_case_workflow_throughput_by_severity(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Severity-split lifecycle latency aggregates for cases in a business.

    Mirrors :func:`summarize_case_workflow_throughput` but groups every count
    and latency aggregate by case severity (info/warning/critical). Operator
    surfaces use this to spot SLA pressure where a few slow info-level cases
    would otherwise mask fast acknowledgment on criticals. Strictly scoped
    per tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    totals_by_severity: dict[str, int] = {}
    ack_by_severity: dict[str, int] = {}
    resolve_by_severity: dict[str, int] = {}
    ack_latencies_by_severity: dict[str, list[int]] = {}
    resolve_latencies_by_severity: dict[str, list[int]] = {}
    for case in cases:
        severity = case.severity
        totals_by_severity[severity] = totals_by_severity.get(severity, 0) + 1
        if case.acknowledged_at is not None:
            ack_latency = int((case.acknowledged_at - case.opened_at).total_seconds())
            ack_by_severity[severity] = ack_by_severity.get(severity, 0) + 1
            ack_latencies_by_severity.setdefault(severity, []).append(ack_latency)
        if case.resolved_at is not None:
            resolve_latency = int((case.resolved_at - case.opened_at).total_seconds())
            resolve_by_severity[severity] = resolve_by_severity.get(severity, 0) + 1
            resolve_latencies_by_severity.setdefault(severity, []).append(resolve_latency)
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "totals_by_severity": totals_by_severity,
            "acknowledged_by_severity": ack_by_severity,
            "resolved_by_severity": resolve_by_severity,
            "time_to_acknowledge_seconds_by_severity": {
                severity: _latency_summary(values)
                for severity, values in ack_latencies_by_severity.items()
            },
            "time_to_resolve_seconds_by_severity": {
                severity: _latency_summary(values)
                for severity, values in resolve_latencies_by_severity.items()
            },
        }
    )


def summarize_case_workflow_throughput_by_case_type(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Case-type-split lifecycle latency aggregates for cases in a business.

    Mirrors :func:`summarize_case_workflow_throughput` but groups every count
    and latency aggregate by case type (sales_drop/stockout_risk/etc.). Lets
    operator surfaces spot which case families are draining acknowledgment or
    resolution time even when severity counts look balanced. Strictly scoped
    per tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    totals_by_case_type: dict[str, int] = {}
    ack_by_case_type: dict[str, int] = {}
    resolve_by_case_type: dict[str, int] = {}
    ack_latencies_by_case_type: dict[str, list[int]] = {}
    resolve_latencies_by_case_type: dict[str, list[int]] = {}
    for case in cases:
        case_type = case.case_type
        totals_by_case_type[case_type] = totals_by_case_type.get(case_type, 0) + 1
        if case.acknowledged_at is not None:
            ack_latency = int((case.acknowledged_at - case.opened_at).total_seconds())
            ack_by_case_type[case_type] = ack_by_case_type.get(case_type, 0) + 1
            ack_latencies_by_case_type.setdefault(case_type, []).append(ack_latency)
        if case.resolved_at is not None:
            resolve_latency = int((case.resolved_at - case.opened_at).total_seconds())
            resolve_by_case_type[case_type] = resolve_by_case_type.get(case_type, 0) + 1
            resolve_latencies_by_case_type.setdefault(case_type, []).append(resolve_latency)
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "totals_by_case_type": totals_by_case_type,
            "acknowledged_by_case_type": ack_by_case_type,
            "resolved_by_case_type": resolve_by_case_type,
            "time_to_acknowledge_seconds_by_case_type": {
                case_type: _latency_summary(values)
                for case_type, values in ack_latencies_by_case_type.items()
            },
            "time_to_resolve_seconds_by_case_type": {
                case_type: _latency_summary(values)
                for case_type, values in resolve_latencies_by_case_type.items()
            },
        }
    )


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
    effective_actor_ref = normalize_operator_actor(actor_ref, actor)

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

from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403


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

def summarize_case_queue(store: OperationalCaseStore, *, business_id: str) -> dict[str, Any]:
    """Deterministic counts over the case queue for a single business.

    Scoped projection: never returns cases from other tenants and never reads
    raw payloads beyond what the case store already exposes. Counts cover the
    full lifecycle (open/acknowledged/in_progress/resolved/dismissed); actionable totals isolate the
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

def summarize_case_queue_by_priority_bracket(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Priority-bracket-split deterministic counts over the case queue.

    Mirrors :func:`summarize_case_queue` but groups lifecycle, actionable, and
    actionable-degraded counts by deterministic priority bracket (``low`` for
    ``priority_score < 50``, ``medium`` for ``50..79``, ``high`` for
    ``80..100``) derived from ``case.priority_score`` via
    :func:`_classify_priority_bracket`. Lets operator surfaces lead with how
    much of the in-flight backlog is high-priority work even when the existing
    severity / case_type counts look healthy. ``total`` counts the full
    lifecycle (open + acknowledged + resolved); ``actionable_*`` counts isolate
    the in-flight slice. Strictly scoped per tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    totals_by_bracket: dict[str, int] = {}
    actionable_by_bracket: dict[str, int] = {}
    actionable_degraded_by_bracket: dict[str, int] = {}
    actionable_total = 0
    for case in cases:
        bracket = _classify_priority_bracket(case.priority_score)
        totals_by_bracket[bracket] = totals_by_bracket.get(bracket, 0) + 1
        if case.status in _ACTIONABLE_STATUSES:
            actionable_total += 1
            actionable_by_bracket[bracket] = actionable_by_bracket.get(bracket, 0) + 1
            if _is_degraded(case):
                actionable_degraded_by_bracket[bracket] = (
                    actionable_degraded_by_bracket.get(bracket, 0) + 1
                )
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "actionable_total": actionable_total,
            "totals_by_priority_bracket": totals_by_bracket,
            "actionable_by_priority_bracket": actionable_by_bracket,
            "actionable_degraded_by_priority_bracket": actionable_degraded_by_bracket,
        }
    )

def summarize_case_queue_by_case_type(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Case-type-split deterministic counts over the case queue.

    Mirrors :func:`summarize_case_queue` but groups lifecycle, actionable, and
    actionable-degraded counts by ``case.case_type``
    (stockout_risk/sales_drop/data_stale/etc.), matching the attribution used
    by :func:`summarize_case_queue_aging_by_case_type` and
    :func:`summarize_case_workflow_throughput_by_case_type`. Lets operator
    surfaces lead with which case family dominates the in-flight backlog even
    when severity / priority distributions look balanced — a stockout_risk
    wave or a data_stale spike often hides inside healthy aggregate counts.
    ``total`` counts the full lifecycle (open + acknowledged + resolved);
    ``actionable_*`` counts isolate the in-flight slice. Strictly scoped per
    tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    totals_by_case_type: dict[str, int] = {}
    actionable_by_case_type: dict[str, int] = {}
    actionable_degraded_by_case_type: dict[str, int] = {}
    actionable_total = 0
    for case in cases:
        case_type = case.case_type
        totals_by_case_type[case_type] = totals_by_case_type.get(case_type, 0) + 1
        if case.status in _ACTIONABLE_STATUSES:
            actionable_total += 1
            actionable_by_case_type[case_type] = (
                actionable_by_case_type.get(case_type, 0) + 1
            )
            if _is_degraded(case):
                actionable_degraded_by_case_type[case_type] = (
                    actionable_degraded_by_case_type.get(case_type, 0) + 1
                )
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "actionable_total": actionable_total,
            "totals_by_case_type": totals_by_case_type,
            "actionable_by_case_type": actionable_by_case_type,
            "actionable_degraded_by_case_type": actionable_degraded_by_case_type,
        }
    )

def summarize_case_queue_by_entity_kind(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Entity-kind-split deterministic counts over the case queue.

    Mirrors :func:`summarize_case_queue` but groups lifecycle, actionable, and
    actionable-degraded counts by ``entity_scope.kind`` (product / channel /
    business / connector / etc.), matching the attribution used by
    :func:`summarize_case_queue_aging_by_entity_kind`,
    :func:`summarize_case_queue_stagnation_by_entity_kind`, and
    :func:`summarize_case_workflow_throughput_by_entity_kind`. Lets operator
    surfaces lead with which scope dominates the in-flight backlog even when
    severity / case_type / source distributions look balanced — for example, a
    wave of product-scoped stockouts often hides inside healthy aggregate
    counts. Cases whose ``entity_scope`` lacks a ``kind`` are bucketed under
    ``"unknown"`` so totals never silently drop. ``total`` counts the full
    lifecycle (open + acknowledged + resolved); ``actionable_*`` counts isolate
    the in-flight slice. Strictly scoped per tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    totals_by_entity_kind: dict[str, int] = {}
    actionable_by_entity_kind: dict[str, int] = {}
    actionable_degraded_by_entity_kind: dict[str, int] = {}
    actionable_total = 0
    for case in cases:
        entity_kind = case.entity_scope.get("kind") or "unknown"
        totals_by_entity_kind[entity_kind] = (
            totals_by_entity_kind.get(entity_kind, 0) + 1
        )
        if case.status in _ACTIONABLE_STATUSES:
            actionable_total += 1
            actionable_by_entity_kind[entity_kind] = (
                actionable_by_entity_kind.get(entity_kind, 0) + 1
            )
            if _is_degraded(case):
                actionable_degraded_by_entity_kind[entity_kind] = (
                    actionable_degraded_by_entity_kind.get(entity_kind, 0) + 1
                )
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "actionable_total": actionable_total,
            "totals_by_entity_kind": totals_by_entity_kind,
            "actionable_by_entity_kind": actionable_by_entity_kind,
            "actionable_degraded_by_entity_kind": actionable_degraded_by_entity_kind,
        }
    )

def summarize_case_queue_by_source_connector(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Source-connector-split deterministic counts over the case queue.

    Mirrors :func:`summarize_case_queue` but groups lifecycle, actionable, and
    actionable-degraded counts by source connector (tiendanube / google_sheets
    / csv / etc.) derived from the alphabetically-first evidence-snapshot
    source via :func:`_source_connectors`, matching the attribution used by
    :func:`summarize_case_queue_aging_by_source_connector` and
    :func:`summarize_case_workflow_throughput_by_source_connector`. Lets
    operator surfaces lead with which ingestion path dominates the in-flight
    backlog even when severity / case_type distributions look balanced — a
    Tiendanube ingestion incident often shows up as a cluster of actionable
    cases skewed to a single source. Cases without any evidence source are
    bucketed under ``"unknown"`` so totals never silently drop. ``total``
    counts the full lifecycle (open + acknowledged + resolved); ``actionable_*``
    counts isolate the in-flight slice. Strictly scoped per tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    totals_by_source: dict[str, int] = {}
    actionable_by_source: dict[str, int] = {}
    actionable_degraded_by_source: dict[str, int] = {}
    actionable_total = 0
    for case in cases:
        sources = _source_connectors(case)
        primary_source = sources[0] if sources else "unknown"
        totals_by_source[primary_source] = totals_by_source.get(primary_source, 0) + 1
        if case.status in _ACTIONABLE_STATUSES:
            actionable_total += 1
            actionable_by_source[primary_source] = (
                actionable_by_source.get(primary_source, 0) + 1
            )
            if _is_degraded(case):
                actionable_degraded_by_source[primary_source] = (
                    actionable_degraded_by_source.get(primary_source, 0) + 1
                )
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "actionable_total": actionable_total,
            "totals_by_source_connector": totals_by_source,
            "actionable_by_source_connector": actionable_by_source,
            "actionable_degraded_by_source_connector": actionable_degraded_by_source,
        }
    )

__all__ = [name for name in globals() if not name.startswith("__")]

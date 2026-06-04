from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403


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


def _latest_in_progress_at(case: OperationalCase) -> datetime | None:
    """Return the latest canonical status-change timestamp for in-progress work."""

    latest: datetime | None = None
    for event in case.timeline:
        if event.event_type != "status_changed":
            continue
        if event.metadata.get("to_status") != "in_progress":
            continue
        created_at = event.created_at.astimezone(timezone.utc)
        if latest is None or created_at > latest:
            latest = created_at
    return latest


def list_recently_in_progress_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
) -> dict[str, Any]:
    """Top-N most-recently-started in-progress cases for a business.

    This projection fills the operator handoff gap between recently acknowledged
    and recently resolved work. It includes only cases whose current status is
    ``in_progress`` and derives the start timestamp from canonical
    ``status_changed`` timeline events rather than ad-hoc surface state. Ordered
    by latest in-progress transition DESC with ``case_id`` ASC as a
    deterministic tie-breaker.
    """

    parsed_limit = parse_limit(limit)
    in_progress: list[tuple[datetime, str, OperationalCase]] = []
    for case in store.list_cases(business_id=business_id, status="in_progress", limit=None):
        in_progress_at = _latest_in_progress_at(case)
        if in_progress_at is None:
            continue
        in_progress.append((in_progress_at, case.case_id, case))

    in_progress.sort(key=lambda item: (-item[0].timestamp(), item[1]))
    limited = in_progress[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "status": case.status,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "opened_at": case.opened_at.isoformat(),
            "in_progress_at": in_progress_at.isoformat(),
            "handling_seconds": int((in_progress_at - case.opened_at).total_seconds()),
        }
        for in_progress_at, _case_id, case in limited
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "in_progress_total": len(in_progress),
            "cases": cases_payload,
            "limit": parsed_limit,
            "count": len(cases_payload),
        }
    )


__all__ = [name for name in globals() if not name.startswith("__")]

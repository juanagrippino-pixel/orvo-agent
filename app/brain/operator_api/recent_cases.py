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


def list_recently_dismissed_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
) -> dict[str, Any]:
    """Top-N most-recently-dismissed cases for a business.

    Dismissed cases are terminal but still operator-relevant: they explain why
    a case left the actionable queue without being resolved. This projection is
    read-only, scoped to one business, ordered by ``dismissed_at`` DESC with
    ``case_id`` ASC as a deterministic tie-breaker, and redacted at the
    boundary so terminal reasons/titles cannot leak secret-shaped strings.
    """

    parsed_limit = parse_limit(limit)
    dismissed: list[tuple[datetime, str, OperationalCase]] = []
    for case in store.list_cases(business_id=business_id, status="dismissed", limit=None):
        if case.dismissed_at is None:
            continue
        dismissed.append((case.dismissed_at.astimezone(timezone.utc), case.case_id, case))

    dismissed.sort(key=lambda item: (-item[0].timestamp(), item[1]))
    limited = dismissed[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "status": case.status,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "opened_at": case.opened_at.isoformat(),
            "dismissed_at": dismissed_at.isoformat(),
            "dismissal_seconds": int((dismissed_at - case.opened_at).total_seconds()),
        }
        for dismissed_at, _case_id, case in limited
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "dismissed_total": len(dismissed),
            "cases": cases_payload,
            "limit": parsed_limit,
            "count": len(cases_payload),
        }
    )


__all__ = [name for name in globals() if not name.startswith("__")]

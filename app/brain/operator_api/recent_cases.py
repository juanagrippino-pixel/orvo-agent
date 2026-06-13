from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _recent_timestamp(item: dict[str, Any], timestamp_key: str) -> str:
    value: Any = item
    for part in timestamp_key.split("."):
        value = value[part]
    return value


def _recent_case_payload(
    *,
    timestamp_key: str,
    duration_key: str,
    total_key: str,
    business_id: str,
    limit: str | None,
    query_result: dict[str, Any],
) -> dict[str, Any]:
    parsed_limit = parse_limit(limit)
    output_timestamp_key = timestamp_key.rsplit(".", 1)[-1]
    cases_payload: list[dict[str, Any]] = []
    for item in query_result["cases"]:
        timestamp_value = _parse_iso(_recent_timestamp(item, timestamp_key))
        opened_at_value = _parse_iso(item["opened_at"])
        cases_payload.append(
            {
                "case_id": item["case_id"],
                "case_type": item["case_type"],
                "status": item["status"],
                "severity": item["severity"],
                "priority_score": item["priority_score"],
                "opened_at": opened_at_value.isoformat(),
                output_timestamp_key: timestamp_value.isoformat(),
                duration_key: int((timestamp_value - opened_at_value).total_seconds()),
            }
        )
    return redact_secrets(
        {
            "business_id": business_id,
            total_key: query_result["total"],
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
    per tenant; filtering and sorting are delegated to the canonical WorkItem
    query layer so endpoint-specific scans cannot drift from built-in views.
    """

    from app.brain.operator_views import query_case_queue

    parsed_limit = parse_limit(limit)
    query_result = query_case_queue(
        store,
        business_id=business_id,
        jql="status = resolved AND resolved_at IS NOT NULL ORDER BY resolved_at DESC",
        limit=str(parsed_limit),
    )
    return _recent_case_payload(
        timestamp_key="work_item.resolved_at",
        duration_key="resolution_seconds",
        total_key="resolved_total",
        business_id=business_id,
        limit=limit,
        query_result=query_result,
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
    deterministic tie-breaker. Strictly scoped per tenant; filtering and sorting
    are delegated to the canonical WorkItem query layer.
    """

    from app.brain.operator_views import query_case_queue

    parsed_limit = parse_limit(limit)
    query_result = query_case_queue(
        store,
        business_id=business_id,
        jql="status = open ORDER BY opened_at DESC",
        limit=str(parsed_limit),
    )
    return _recent_case_payload(
        timestamp_key="opened_at",
        duration_key="age_seconds",
        total_key="open_total",
        business_id=business_id,
        limit=limit,
        query_result=query_result,
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
    without extra lookups. Strictly scoped per tenant; filtering and sorting are
    delegated to the canonical WorkItem query layer.
    """

    from app.brain.operator_views import query_case_queue

    parsed_limit = parse_limit(limit)
    query_result = query_case_queue(
        store,
        business_id=business_id,
        jql="status = acknowledged AND acknowledged_at IS NOT NULL ORDER BY acknowledged_at DESC",
        limit=str(parsed_limit),
    )
    return _recent_case_payload(
        timestamp_key="acknowledged_at",
        duration_key="acknowledgment_seconds",
        total_key="acknowledged_total",
        business_id=business_id,
        limit=limit,
        query_result=query_result,
    )


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
    ``status_changed`` timeline events through the WorkItem query field registry.
    Ordered by latest in-progress transition DESC with ``case_id`` ASC as a
    deterministic tie-breaker.
    """

    from app.brain.operator_views import query_case_queue

    parsed_limit = parse_limit(limit)
    query_result = query_case_queue(
        store,
        business_id=business_id,
        jql="status = in_progress AND in_progress_at IS NOT NULL ORDER BY in_progress_at DESC",
        limit=str(parsed_limit),
    )
    return _recent_case_payload(
        timestamp_key="work_item.in_progress_at",
        duration_key="handling_seconds",
        total_key="in_progress_total",
        business_id=business_id,
        limit=limit,
        query_result=query_result,
    )


__all__ = [name for name in globals() if not name.startswith("__")]

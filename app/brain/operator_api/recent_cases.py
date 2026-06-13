from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403


def _case_terminal_reason(case: OperationalCase, terminal_status: str) -> str | None:
    """Return the redacted reason summary for a terminal status transition."""

    for event in reversed(case.timeline):
        if event.event_type != "status_changed":
            continue
        if event.metadata.get("to_status") != terminal_status:
            continue
        return redact_text(event.summary)
    return None


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
            "terminal_reason": _case_terminal_reason(case, "resolved"),
        }
        for _resolved_at, _case_id, case in limited
    ]
    return build_recent_case_activity_payload(
        business_id=business_id,
        activity_type="resolved",
        legacy_total_key="resolved_total",
        total=len(resolved),
        cases_payload=cases_payload,
        limit=parsed_limit,
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
    return build_recent_case_activity_payload(
        business_id=business_id,
        activity_type="opened",
        legacy_total_key="open_total",
        total=len(opened),
        cases_payload=cases_payload,
        limit=parsed_limit,
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
    return build_recent_case_activity_payload(
        business_id=business_id,
        activity_type="acknowledged",
        legacy_total_key="acknowledged_total",
        total=len(acknowledged),
        cases_payload=cases_payload,
        limit=parsed_limit,
    )

def list_recently_assigned_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
) -> dict[str, Any]:
    """Top-N most-recently-assigned actionable cases for a business.

    Assignment is an operator ownership projection, not a lifecycle source of
    truth. Include only currently-actionable cases so closed work remains owned
    by terminal projections; order by ``assigned_at`` DESC with ``case_id`` ASC
    as a deterministic tie-breaker. Assignee refs are already redacted before
    persistence, and the whole payload is redacted again at the surface boundary.
    """

    parsed_limit = parse_limit(limit)
    assigned: list[tuple[datetime, str, OperationalCase]] = []
    for status in ("open", "acknowledged", "in_progress"):
        for case in store.list_cases(business_id=business_id, status=status, limit=None):
            if case.assigned_at is None:
                continue
            assigned.append((case.assigned_at.astimezone(timezone.utc), case.case_id, case))

    assigned.sort(key=lambda item: (-item[0].timestamp(), item[1]))
    limited = assigned[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "status": case.status,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "opened_at": case.opened_at.isoformat(),
            "assigned_at": assigned_at.isoformat(),
            "assignee_ref": case.assignee_ref,
            "assignment_seconds": int((assigned_at - case.opened_at).total_seconds()),
        }
        for assigned_at, _case_id, case in limited
    ]
    return build_recent_case_activity_payload(
        business_id=business_id,
        activity_type="assigned",
        legacy_total_key="assigned_total",
        total=len(assigned),
        cases_payload=cases_payload,
        limit=parsed_limit,
    )

def _latest_transition_to_at(case: OperationalCase, status: str) -> datetime | None:
    """Return the latest canonical status-change timestamp for a status."""

    latest: datetime | None = None
    for event in case.timeline:
        if event.event_type != "status_changed":
            continue
        if event.metadata.get("to_status") != status:
            continue
        created_at = event.created_at.astimezone(timezone.utc)
        if latest is None or created_at > latest:
            latest = created_at
    return latest


def _case_transitioned_to_at(case: OperationalCase, status: str) -> datetime:
    """Return canonical transition timestamp with a legacy fixture fallback.

    ``in_progress`` has no dedicated model timestamp yet. The case timeline is
    the source of truth for lifecycle events, so derive the projection timestamp
    from status-change events. ``updated_at`` remains a backward-compatible
    fallback for older fixtures that predate timeline metadata.
    """

    return _latest_transition_to_at(case, status) or case.updated_at.astimezone(timezone.utc)


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
        in_progress_at = _case_transitioned_to_at(case, "in_progress")
        in_progress.append((in_progress_at.astimezone(timezone.utc), case.case_id, case))

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
            "time_to_in_progress_seconds": int((in_progress_at - case.opened_at).total_seconds()),
        }
        for in_progress_at, _case_id, case in limited
    ]
    return build_recent_case_activity_payload(
        business_id=business_id,
        activity_type="in_progress",
        legacy_total_key="in_progress_total",
        total=len(in_progress),
        cases_payload=cases_payload,
        limit=parsed_limit,
    )


def list_recently_reopened_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
) -> dict[str, Any]:
    """Top-N recently-reopened actionable cases for a business.

    Reopened cases are recurrence signals emitted by the canonical case store
    when a deterministic detection returns after a terminal state. This
    read-only projection keeps operator queues focused on actionable recurrences:
    it includes only non-terminal cases with a ``case_reopened`` timeline event,
    orders by the latest reopen timestamp DESC with ``case_id`` ASC as a stable
    tie-breaker, and redacts at the API boundary.
    """

    parsed_limit = parse_limit(limit)
    reopened: list[tuple[datetime, str, OperationalCase]] = []
    for status in ("open", "acknowledged", "in_progress"):
        for case in store.list_cases(business_id=business_id, status=status, limit=None):
            reopened_events = [event.created_at for event in case.timeline if event.event_type == "case_reopened"]
            if not reopened_events:
                continue
            reopened_at = max(event.astimezone(timezone.utc) for event in reopened_events)
            reopened.append((reopened_at, case.case_id, case))

    reopened.sort(key=lambda item: (-item[0].timestamp(), item[1]))
    limited = reopened[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "status": case.status,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "opened_at": case.opened_at.isoformat(),
            "reopened_at": reopened_at.isoformat(),
            "time_to_reopen_seconds": int((reopened_at - case.opened_at).total_seconds()),
        }
        for reopened_at, _case_id, case in limited
    ]
    return build_recent_case_activity_payload(
        business_id=business_id,
        activity_type="reopened",
        legacy_total_key="reopened_total",
        total=len(reopened),
        cases_payload=cases_payload,
        limit=parsed_limit,
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
            "terminal_reason": _case_terminal_reason(case, "dismissed"),
        }
        for dismissed_at, _case_id, case in limited
    ]
    return build_recent_case_activity_payload(
        business_id=business_id,
        activity_type="dismissed",
        legacy_total_key="dismissed_total",
        total=len(dismissed),
        cases_payload=cases_payload,
        limit=parsed_limit,
    )


__all__ = [name for name in globals() if not name.startswith("__")]

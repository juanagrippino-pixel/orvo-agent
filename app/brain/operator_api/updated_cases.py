from __future__ import annotations

from .common import *  # noqa: F401,F403


def _latest_timeline_event(case: OperationalCase) -> Any | None:
    """Return the latest canonical timeline event for a case, if present."""

    if not case.timeline:
        return None
    return max(
        case.timeline,
        key=lambda event: (event.created_at.astimezone(timezone.utc).timestamp(), event.event_id),
    )


def list_recently_updated_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
) -> dict[str, Any]:
    """Top-N cases with the most recent canonical timeline activity.

    This is a read-only operator activity feed over ``OperationalCase`` timeline
    events. It does not infer lifecycle state from presentation text: the latest
    activity row is derived from the canonical case timeline, ordered by latest
    event timestamp DESC with ``case_id`` ASC as the deterministic tie-breaker,
    scoped to one business, and redacted again at the API boundary.
    """

    parsed_limit = parse_limit(limit)
    updated: list[tuple[datetime, str, OperationalCase, Any]] = []
    for case in store.list_cases(business_id=business_id, limit=None):
        latest_event = _latest_timeline_event(case)
        if latest_event is None:
            continue
        latest_at = latest_event.created_at.astimezone(timezone.utc)
        updated.append((latest_at, case.case_id, case, latest_event))

    updated.sort(key=lambda item: (-item[0].timestamp(), item[1]))
    limited = updated[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "title": case.title,
            "entity_scope": case.entity_scope,
            "status": case.status,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "opened_at": case.opened_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
            "latest_activity_at": latest_at.isoformat(),
            "latest_activity_type": latest_event.event_type,
            "latest_activity_summary": latest_event.summary,
            "latest_activity_actor_type": latest_event.actor_type,
            "latest_activity_actor_ref": latest_event.actor_ref,
            "latest_activity_event_id": latest_event.event_id,
            "timeline_event_count": len(case.timeline),
        }
        for latest_at, _case_id, case, latest_event in limited
    ]
    return build_recent_case_activity_payload(
        business_id=business_id,
        activity_type="updated",
        legacy_total_key="updated_total",
        total=len(updated),
        cases_payload=cases_payload,
        limit=parsed_limit,
    )


__all__ = [name for name in globals() if not name.startswith("__")]

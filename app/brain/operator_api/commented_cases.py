from __future__ import annotations

from .common import *  # noqa: F401,F403


def list_recently_commented_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
) -> dict[str, Any]:
    """Top-N cases with the most recent operator comments for a business.

    Comments live on the canonical case timeline, so this is a read-only
    collaboration projection over ``operator_comment`` events rather than a
    lifecycle source of truth. Each case appears once, ordered by its latest
    operator comment DESC with ``case_id`` ASC as the deterministic tie-breaker.
    Comment text and actor refs are redacted by the case model and again at the
    surface boundary.
    """

    parsed_limit = parse_limit(limit)
    commented: list[tuple[datetime, str, OperationalCase, list[Any]]] = []
    for case in store.list_cases(business_id=business_id, limit=None):
        comment_events = [event for event in case.timeline if event.event_type == "operator_comment"]
        if not comment_events:
            continue
        latest_comment = max(
            comment_events,
            key=lambda event: event.created_at.astimezone(timezone.utc).timestamp(),
        )
        commented.append(
            (
                latest_comment.created_at.astimezone(timezone.utc),
                case.case_id,
                case,
                comment_events,
            )
        )

    commented.sort(key=lambda item: (-item[0].timestamp(), item[1]))
    limited = commented[:parsed_limit]
    cases_payload = []
    for latest_comment_at, _case_id, case, comment_events in limited:
        latest_comment = max(
            comment_events,
            key=lambda event: event.created_at.astimezone(timezone.utc).timestamp(),
        )
        cases_payload.append(
            {
                "case_id": case.case_id,
                "case_type": case.case_type,
                "status": case.status,
                "severity": case.severity,
                "priority_score": case.priority_score,
                "opened_at": case.opened_at.isoformat(),
                "latest_comment_at": latest_comment_at.isoformat(),
                "latest_comment_summary": latest_comment.summary,
                "latest_comment_actor_ref": latest_comment.actor_ref,
                "comment_count": len(comment_events),
            }
        )

    return redact_secrets(
        {
            "business_id": business_id,
            "commented_total": len(commented),
            "cases": cases_payload,
            "limit": parsed_limit,
            "count": len(cases_payload),
        }
    )

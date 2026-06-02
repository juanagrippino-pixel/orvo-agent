from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403


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
    by priority as often as by age, so this projection ranks open, acknowledged,
    and in-progress cases by ``priority_score`` DESC. Ties on priority are broken
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

__all__ = [name for name in globals() if not name.startswith("__")]

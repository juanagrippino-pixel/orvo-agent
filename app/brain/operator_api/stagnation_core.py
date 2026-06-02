from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403


def summarize_case_queue_stagnation(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Deterministic idleness histogram for actionable cases in a business.

    Aggregate counterpart to :func:`list_top_stalled_actionable_cases`: buckets
    actionable (open + acknowledged + in_progress) cases by ``now - updated_at`` so operator
    surfaces can see how many cases have not been touched in each time window
    without paging through a long top-N list. Severity is split per bucket so
    operators can tell whether old idle work is critical or informational.
    ``opened_at`` is reported on the most-stalled row for triage context but
    does not influence bucket assignment. Strictly scoped per tenant; ``now``
    is injectable for deterministic tests and defaults to current UTC.
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
    most_stalled_idle = -1
    most_stalled_case: OperationalCase | None = None
    most_stalled_age = 0
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        actionable_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        updated_at = case.updated_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        idle_seconds = max(int((reference - updated_at).total_seconds()), 0)
        bucket = _classify_age_bucket(idle_seconds)
        buckets[bucket] += 1
        severity_counts = severity_by_bucket[bucket]
        severity_counts[case.severity] = severity_counts.get(case.severity, 0) + 1
        if idle_seconds > most_stalled_idle:
            most_stalled_idle = idle_seconds
            most_stalled_case = case
            most_stalled_age = age_seconds
    most_stalled_payload: dict[str, Any] | None = None
    if most_stalled_case is not None:
        most_stalled_payload = {
            "case_id": most_stalled_case.case_id,
            "case_type": most_stalled_case.case_type,
            "status": most_stalled_case.status,
            "severity": most_stalled_case.severity,
            "opened_at": most_stalled_case.opened_at.isoformat(),
            "updated_at": most_stalled_case.updated_at.isoformat(),
            "idle_seconds": most_stalled_idle,
            "age_seconds": most_stalled_age,
        }
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": actionable_total,
            "by_idle_bucket": buckets,
            "by_idle_bucket_severity": severity_by_bucket,
            "most_stalled_actionable": most_stalled_payload,
        }
    )

def summarize_case_queue_stagnation_by_case_type(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Case-type-split idleness histogram for actionable cases in a business.

    Mirrors :func:`summarize_case_queue_stagnation` but groups each idleness
    bucket by case type instead of severity, so operator surfaces can see which
    case families dominate the un-touched backlog at every idleness horizon.
    ``opened_at`` is reported on the most-stalled row for triage context but
    does not influence bucket assignment. Strictly scoped per tenant; ``now``
    is injectable for deterministic tests and defaults to current UTC.
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
    most_stalled_idle = -1
    most_stalled_case: OperationalCase | None = None
    most_stalled_age = 0
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        actionable_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        updated_at = case.updated_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        idle_seconds = max(int((reference - updated_at).total_seconds()), 0)
        bucket = _classify_age_bucket(idle_seconds)
        buckets[bucket] += 1
        case_type_counts = case_type_by_bucket[bucket]
        case_type_counts[case.case_type] = case_type_counts.get(case.case_type, 0) + 1
        if idle_seconds > most_stalled_idle:
            most_stalled_idle = idle_seconds
            most_stalled_case = case
            most_stalled_age = age_seconds
    most_stalled_payload: dict[str, Any] | None = None
    if most_stalled_case is not None:
        most_stalled_payload = {
            "case_id": most_stalled_case.case_id,
            "case_type": most_stalled_case.case_type,
            "status": most_stalled_case.status,
            "severity": most_stalled_case.severity,
            "opened_at": most_stalled_case.opened_at.isoformat(),
            "updated_at": most_stalled_case.updated_at.isoformat(),
            "idle_seconds": most_stalled_idle,
            "age_seconds": most_stalled_age,
        }
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": actionable_total,
            "by_idle_bucket": buckets,
            "by_idle_bucket_case_type": case_type_by_bucket,
            "most_stalled_actionable": most_stalled_payload,
        }
    )

def summarize_case_queue_stagnation_by_entity_kind(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Entity-kind-split idleness histogram for actionable cases in a business.

    Mirrors :func:`summarize_case_queue_stagnation` but groups each idleness
    bucket by ``entity_scope.kind`` (product/channel/business/etc.) instead of
    severity, so operator surfaces can see which scopes dominate the un-touched
    backlog at every idleness horizon. Cases missing a ``kind`` are bucketed
    under ``"unknown"`` so totals never silently drop. ``opened_at`` is reported
    on the most-stalled row for triage context but does not influence bucket
    assignment. Strictly scoped per tenant; ``now`` is injectable for
    deterministic tests and defaults to current UTC.
    """

    if now is None:
        reference = _now_utc()
    else:
        if now.tzinfo is None or now.utcoffset() is None:
            raise OperatorAPIError("invalid_now", "now must be timezone-aware", status_code=400)
        reference = now.astimezone(timezone.utc)

    buckets: dict[str, int] = {name: 0 for name, _ in _AGE_BUCKETS}
    entity_kind_by_bucket: dict[str, dict[str, int]] = {name: {} for name, _ in _AGE_BUCKETS}
    actionable_total = 0
    most_stalled_idle = -1
    most_stalled_case: OperationalCase | None = None
    most_stalled_age = 0
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        actionable_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        updated_at = case.updated_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        idle_seconds = max(int((reference - updated_at).total_seconds()), 0)
        bucket = _classify_age_bucket(idle_seconds)
        buckets[bucket] += 1
        entity_kind = case.entity_scope.get("kind") or "unknown"
        entity_kind_counts = entity_kind_by_bucket[bucket]
        entity_kind_counts[entity_kind] = entity_kind_counts.get(entity_kind, 0) + 1
        if idle_seconds > most_stalled_idle:
            most_stalled_idle = idle_seconds
            most_stalled_case = case
            most_stalled_age = age_seconds
    most_stalled_payload: dict[str, Any] | None = None
    if most_stalled_case is not None:
        most_stalled_payload = {
            "case_id": most_stalled_case.case_id,
            "case_type": most_stalled_case.case_type,
            "status": most_stalled_case.status,
            "severity": most_stalled_case.severity,
            "opened_at": most_stalled_case.opened_at.isoformat(),
            "updated_at": most_stalled_case.updated_at.isoformat(),
            "idle_seconds": most_stalled_idle,
            "age_seconds": most_stalled_age,
        }
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": actionable_total,
            "by_idle_bucket": buckets,
            "by_idle_bucket_entity_kind": entity_kind_by_bucket,
            "most_stalled_actionable": most_stalled_payload,
        }
    )

__all__ = [name for name in globals() if not name.startswith("__")]

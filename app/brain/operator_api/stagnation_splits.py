from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403


def summarize_case_queue_stagnation_by_source_connector(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Source-connector-split idleness histogram for actionable cases in a business.

    Mirrors :func:`summarize_case_queue_stagnation` but groups each idleness
    bucket by source connector (tiendanube/google_sheets/csv/etc.), so operator
    surfaces can see which connectors dominate the un-touched backlog at every
    idleness horizon — for example, a Tiendanube ingestion incident often shows
    up as a cluster of idle cases skewed to a single source even when severity
    and case_type distributions look balanced. Each case is attributed to a
    single connector — the alphabetically-first source from its evidence
    snapshots, matching
    :func:`summarize_case_queue_aging_by_source_connector` and
    :func:`summarize_case_workflow_throughput_by_source_connector` — so the
    per-bucket totals always sum exactly to ``actionable_total``. Cases without
    any evidence source are bucketed under ``"unknown"`` so totals never
    silently drop. ``opened_at`` is reported on the most-stalled row for triage
    context but does not influence bucket assignment. Strictly scoped per
    tenant; ``now`` is injectable for deterministic tests and defaults to
    current UTC.
    """

    if now is None:
        reference = _now_utc()
    else:
        if now.tzinfo is None or now.utcoffset() is None:
            raise OperatorAPIError("invalid_now", "now must be timezone-aware", status_code=400)
        reference = now.astimezone(timezone.utc)

    buckets: dict[str, int] = {name: 0 for name, _ in _AGE_BUCKETS}
    source_by_bucket: dict[str, dict[str, int]] = {name: {} for name, _ in _AGE_BUCKETS}
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
        sources = _source_connectors(case)
        primary_source = sources[0] if sources else "unknown"
        source_counts = source_by_bucket[bucket]
        source_counts[primary_source] = source_counts.get(primary_source, 0) + 1
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
            "by_idle_bucket_source_connector": source_by_bucket,
            "most_stalled_actionable": most_stalled_payload,
        }
    )

def summarize_case_queue_stagnation_by_priority_bracket(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Priority-bracket-split idleness histogram for actionable cases in a business.

    Mirrors :func:`summarize_case_queue_stagnation_by_source_connector` but
    groups each idleness bucket by deterministic priority bracket (``low`` for
    ``priority_score < 50``, ``medium`` for ``50..79``, ``high`` for
    ``80..100``) derived from ``case.priority_score`` instead of source
    connector. Operator surfaces use it to spot when the un-touched backlog is
    skewed toward high-priority work even when the overall idleness
    distribution and case_type / entity_kind / source-connector splits look
    healthy. Idleness is driven by ``updated_at``, so a recently-acknowledged
    old case is reported as freshly handled; ``opened_at`` is reported on the
    most-stalled row for triage context but does not influence bucket
    assignment. Open, acknowledged, and in-progress cases are counted as actionable.
    Strictly scoped per tenant; ``now`` is injectable for deterministic tests
    and defaults to current UTC.
    """

    if now is None:
        reference = _now_utc()
    else:
        if now.tzinfo is None or now.utcoffset() is None:
            raise OperatorAPIError("invalid_now", "now must be timezone-aware", status_code=400)
        reference = now.astimezone(timezone.utc)

    buckets: dict[str, int] = {name: 0 for name, _ in _AGE_BUCKETS}
    bracket_by_bucket: dict[str, dict[str, int]] = {name: {} for name, _ in _AGE_BUCKETS}
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
        bracket = _classify_priority_bracket(case.priority_score)
        bracket_counts = bracket_by_bucket[bucket]
        bracket_counts[bracket] = bracket_counts.get(bracket, 0) + 1
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
            "by_idle_bucket_priority_bracket": bracket_by_bucket,
            "most_stalled_actionable": most_stalled_payload,
        }
    )

def summarize_case_queue_stagnation_by_severity(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Severity-split idleness histogram for actionable cases in a business.

    Mirrors :func:`summarize_case_queue_stagnation_by_priority_bracket` but
    groups each idleness bucket by case severity (info / warning / critical)
    instead of priority bracket, matching the attribution used by
    :func:`summarize_case_queue_aging_by_severity` and
    :func:`summarize_case_workflow_throughput_by_severity`. Operator surfaces
    use it to spot when criticals are sitting un-touched even when the overall
    idleness distribution and case_type / entity_kind / source-connector /
    priority-bracket splits look healthy — a single old idle ``critical``
    hiding in ``over_7d`` is materially different from an old idle ``info``
    there. Idleness is driven by ``updated_at``, so a recently-acknowledged
    old case is reported as freshly handled; ``opened_at`` is reported on the
    most-stalled row for triage context but does not influence bucket
    assignment. Open and acknowledged cases are both counted as actionable.
    Strictly scoped per tenant; ``now`` is injectable for deterministic tests
    and defaults to current UTC.
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

__all__ = [name for name in globals() if not name.startswith("__")]

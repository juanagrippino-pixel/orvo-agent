from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403


def summarize_case_queue_aging(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Deterministic age histogram for actionable cases in a business.

    Buckets actionable (open + acknowledged + in_progress) cases by ``now - opened_at`` so
    operator surfaces can see how stale the in-flight workload is. Strictly
    scoped per tenant; ``now`` is injectable for deterministic tests and
    defaults to current UTC.
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
    oldest_age = -1
    oldest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        actionable_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(age_seconds)
        buckets[bucket] += 1
        severity_counts = severity_by_bucket[bucket]
        severity_counts[case.severity] = severity_counts.get(case.severity, 0) + 1
        if age_seconds > oldest_age:
            oldest_age = age_seconds
            oldest_case = case
    oldest_payload: dict[str, Any] | None = None
    if oldest_case is not None:
        oldest_payload = {
            "case_id": oldest_case.case_id,
            "case_type": oldest_case.case_type,
            "status": oldest_case.status,
            "severity": oldest_case.severity,
            "opened_at": oldest_case.opened_at.isoformat(),
            "age_seconds": oldest_age,
        }
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": actionable_total,
            "by_age_bucket": buckets,
            "by_age_bucket_severity": severity_by_bucket,
            "oldest_actionable": oldest_payload,
        }
    )

def summarize_case_queue_aging_by_case_type(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Case-type-split age histogram for actionable cases in a business.

    Mirrors :func:`summarize_case_queue_aging` but groups each age bucket by
    case type instead of severity, so operator surfaces can see which case
    families dominate the in-flight backlog at every age horizon. Strictly
    scoped per tenant; ``now`` is injectable for deterministic tests and
    defaults to current UTC.
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
    oldest_age = -1
    oldest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        actionable_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(age_seconds)
        buckets[bucket] += 1
        case_type_counts = case_type_by_bucket[bucket]
        case_type_counts[case.case_type] = case_type_counts.get(case.case_type, 0) + 1
        if age_seconds > oldest_age:
            oldest_age = age_seconds
            oldest_case = case
    oldest_payload: dict[str, Any] | None = None
    if oldest_case is not None:
        oldest_payload = {
            "case_id": oldest_case.case_id,
            "case_type": oldest_case.case_type,
            "status": oldest_case.status,
            "severity": oldest_case.severity,
            "opened_at": oldest_case.opened_at.isoformat(),
            "age_seconds": oldest_age,
        }
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": actionable_total,
            "by_age_bucket": buckets,
            "by_age_bucket_case_type": case_type_by_bucket,
            "oldest_actionable": oldest_payload,
        }
    )

def summarize_case_queue_aging_by_source_connector(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Source-connector-split age histogram for actionable cases in a business.

    Mirrors :func:`summarize_case_queue_aging` but groups each age bucket by
    source connector (tiendanube/google_sheets/csv/etc.), so operator surfaces
    can see which connectors dominate the in-flight backlog at every age
    horizon — for example, a Tiendanube ingestion incident often shows up as
    aging cases skewed to a single source even when severity and case_type
    distributions look balanced. Each case is attributed to a single connector
    — the alphabetically-first source from its evidence snapshots, matching
    :func:`summarize_case_workflow_throughput_by_source_connector` — so the
    per-bucket totals always sum exactly to ``actionable_total``. Cases without
    any evidence source are bucketed under ``"unknown"`` so totals never
    silently drop. Strictly scoped per tenant; ``now`` is injectable for
    deterministic tests and defaults to current UTC.
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
    oldest_age = -1
    oldest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        actionable_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(age_seconds)
        buckets[bucket] += 1
        sources = _source_connectors(case)
        primary_source = sources[0] if sources else "unknown"
        source_counts = source_by_bucket[bucket]
        source_counts[primary_source] = source_counts.get(primary_source, 0) + 1
        if age_seconds > oldest_age:
            oldest_age = age_seconds
            oldest_case = case
    oldest_payload: dict[str, Any] | None = None
    if oldest_case is not None:
        oldest_payload = {
            "case_id": oldest_case.case_id,
            "case_type": oldest_case.case_type,
            "status": oldest_case.status,
            "severity": oldest_case.severity,
            "opened_at": oldest_case.opened_at.isoformat(),
            "age_seconds": oldest_age,
        }
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": actionable_total,
            "by_age_bucket": buckets,
            "by_age_bucket_source_connector": source_by_bucket,
            "oldest_actionable": oldest_payload,
        }
    )

def summarize_case_queue_aging_by_entity_kind(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Entity-kind-split age histogram for actionable cases in a business.

    Mirrors :func:`summarize_case_queue_aging` but groups each age bucket by
    ``entity_scope.kind`` (product/channel/business/etc.) instead of severity,
    so operator surfaces can see which scopes dominate the in-flight backlog at
    every age horizon. Cases missing a ``kind`` are bucketed under ``"unknown"``
    so totals never silently drop. Strictly scoped per tenant; ``now`` is
    injectable for deterministic tests and defaults to current UTC.
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
    oldest_age = -1
    oldest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        actionable_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(age_seconds)
        buckets[bucket] += 1
        entity_kind = case.entity_scope.get("kind") or "unknown"
        entity_kind_counts = entity_kind_by_bucket[bucket]
        entity_kind_counts[entity_kind] = entity_kind_counts.get(entity_kind, 0) + 1
        if age_seconds > oldest_age:
            oldest_age = age_seconds
            oldest_case = case
    oldest_payload: dict[str, Any] | None = None
    if oldest_case is not None:
        oldest_payload = {
            "case_id": oldest_case.case_id,
            "case_type": oldest_case.case_type,
            "status": oldest_case.status,
            "severity": oldest_case.severity,
            "opened_at": oldest_case.opened_at.isoformat(),
            "age_seconds": oldest_age,
        }
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": actionable_total,
            "by_age_bucket": buckets,
            "by_age_bucket_entity_kind": entity_kind_by_bucket,
            "oldest_actionable": oldest_payload,
        }
    )

def summarize_case_queue_aging_by_priority_bracket(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Priority-bracket-split age histogram for actionable cases in a business.

    Mirrors :func:`summarize_case_queue_aging_by_source_connector` but groups
    each age bucket by deterministic priority bracket (``low`` for
    ``priority_score < 50``, ``medium`` for ``50..79``, ``high`` for
    ``80..100``) derived from ``case.priority_score`` instead of source
    connector. Operator surfaces use it to spot when the in-flight backlog
    is skewed toward high-priority work even when the overall age
    distribution and case_type / entity_kind / source-connector splits look
    healthy. Open, acknowledged, and in-progress cases are counted as actionable.
    Strictly scoped per tenant; ``now`` is injectable for deterministic
    tests and defaults to current UTC.
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
    oldest_age = -1
    oldest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        actionable_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(age_seconds)
        buckets[bucket] += 1
        bracket = _classify_priority_bracket(case.priority_score)
        bracket_counts = bracket_by_bucket[bucket]
        bracket_counts[bracket] = bracket_counts.get(bracket, 0) + 1
        if age_seconds > oldest_age:
            oldest_age = age_seconds
            oldest_case = case
    oldest_payload: dict[str, Any] | None = None
    if oldest_case is not None:
        oldest_payload = {
            "case_id": oldest_case.case_id,
            "case_type": oldest_case.case_type,
            "status": oldest_case.status,
            "severity": oldest_case.severity,
            "opened_at": oldest_case.opened_at.isoformat(),
            "age_seconds": oldest_age,
        }
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": actionable_total,
            "by_age_bucket": buckets,
            "by_age_bucket_priority_bracket": bracket_by_bucket,
            "oldest_actionable": oldest_payload,
        }
    )

def summarize_case_queue_aging_by_severity(
    store: OperationalCaseStore,
    *,
    business_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Severity-split age histogram for actionable cases in a business.

    Mirrors :func:`summarize_case_queue_aging_by_priority_bracket` but groups
    each age bucket by case severity (info / warning / critical) instead of
    priority bracket, matching the attribution used by
    :func:`summarize_case_workflow_throughput_by_severity`. Operator surfaces
    use it to spot when criticals are aging dangerously even when the overall
    age distribution and case_type / entity_kind / source-connector /
    priority-bracket splits look healthy — a single old ``critical`` hiding in
    ``over_7d`` is materially different from an old ``info`` there. Open and
    acknowledged cases are both counted as actionable. Strictly scoped per
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
    severity_by_bucket: dict[str, dict[str, int]] = {name: {} for name, _ in _AGE_BUCKETS}
    actionable_total = 0
    oldest_age = -1
    oldest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        actionable_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        age_seconds = max(int((reference - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(age_seconds)
        buckets[bucket] += 1
        severity = case.severity
        severity_counts = severity_by_bucket[bucket]
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        if age_seconds > oldest_age:
            oldest_age = age_seconds
            oldest_case = case
    oldest_payload: dict[str, Any] | None = None
    if oldest_case is not None:
        oldest_payload = {
            "case_id": oldest_case.case_id,
            "case_type": oldest_case.case_type,
            "status": oldest_case.status,
            "severity": oldest_case.severity,
            "opened_at": oldest_case.opened_at.isoformat(),
            "age_seconds": oldest_age,
        }
    return redact_secrets(
        {
            "business_id": business_id,
            "now": reference.isoformat(),
            "actionable_total": actionable_total,
            "by_age_bucket": buckets,
            "by_age_bucket_severity": severity_by_bucket,
            "oldest_actionable": oldest_payload,
        }
    )

__all__ = [name for name in globals() if not name.startswith("__")]

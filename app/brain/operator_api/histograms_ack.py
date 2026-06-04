from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403


def summarize_case_acknowledgment_latency_histogram(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Deterministic histogram of time-to-acknowledge for acknowledged cases.

    Symmetric to :func:`summarize_case_resolution_latency_histogram`: this
    projection buckets each acknowledged case's ``acknowledged_at -
    opened_at`` latency into the same age horizons used by
    :func:`summarize_case_queue_aging` so operator surfaces can see the
    *shape* of acknowledgment time — exposing a long tail of over-7d
    acknowledgments that the central-tendency stats in
    :func:`summarize_case_workflow_throughput` would otherwise mask. Severity
    is split per bucket so SLA pressure on critical work is visible even when
    informational backlog dominates the histogram. Cases that were resolved
    after acknowledgment are still counted (they were acknowledged at some
    point); only open-only cases without ``acknowledged_at`` are excluded.
    Strictly scoped per tenant.
    """

    buckets: dict[str, int] = {name: 0 for name, _ in _AGE_BUCKETS}
    severity_by_bucket: dict[str, dict[str, int]] = {name: {} for name, _ in _AGE_BUCKETS}
    acknowledged_total = 0
    fastest_seconds = -1
    fastest_case: OperationalCase | None = None
    slowest_seconds = -1
    slowest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.acknowledged_at is None:
            continue
        acknowledged_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        acknowledged_at = case.acknowledged_at.astimezone(timezone.utc)
        time_to_ack = max(int((acknowledged_at - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(time_to_ack)
        buckets[bucket] += 1
        severity_counts = severity_by_bucket[bucket]
        severity_counts[case.severity] = severity_counts.get(case.severity, 0) + 1
        if fastest_seconds < 0 or time_to_ack < fastest_seconds:
            fastest_seconds = time_to_ack
            fastest_case = case
        if time_to_ack > slowest_seconds:
            slowest_seconds = time_to_ack
            slowest_case = case

    def _payload(case: OperationalCase | None, seconds: int) -> dict[str, Any] | None:
        if case is None or case.acknowledged_at is None:
            return None
        return {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "severity": case.severity,
            "opened_at": case.opened_at.isoformat(),
            "acknowledged_at": case.acknowledged_at.isoformat(),
            "time_to_acknowledge_seconds": seconds,
        }

    return redact_secrets(
        {
            "business_id": business_id,
            "acknowledged_total": acknowledged_total,
            "by_acknowledgment_bucket": buckets,
            "by_acknowledgment_bucket_severity": severity_by_bucket,
            "fastest_acknowledged": _payload(fastest_case, fastest_seconds),
            "slowest_acknowledged": _payload(slowest_case, slowest_seconds),
        }
    )

def summarize_case_acknowledgment_latency_histogram_by_case_type(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Case-type-split deterministic histogram of time-to-acknowledge.

    Mirrors :func:`summarize_case_acknowledgment_latency_histogram_by_case_type`'s
    resolution counterpart (:func:`summarize_case_resolution_latency_histogram_by_case_type`)
    but groups each acknowledgment-latency bucket by case type instead of severity,
    so operator surfaces can see which case families dominate slow-ack tails —
    e.g. a healthy median that masks a stockout_risk over-7d tail of pickups.
    Cases that were resolved after acknowledgment are still counted (they were
    acknowledged at some point); only open-only cases without ``acknowledged_at``
    are excluded. Strictly scoped per tenant.
    """

    buckets: dict[str, int] = {name: 0 for name, _ in _AGE_BUCKETS}
    case_type_by_bucket: dict[str, dict[str, int]] = {name: {} for name, _ in _AGE_BUCKETS}
    acknowledged_total = 0
    fastest_seconds = -1
    fastest_case: OperationalCase | None = None
    slowest_seconds = -1
    slowest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.acknowledged_at is None:
            continue
        acknowledged_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        acknowledged_at = case.acknowledged_at.astimezone(timezone.utc)
        time_to_ack = max(int((acknowledged_at - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(time_to_ack)
        buckets[bucket] += 1
        case_type_counts = case_type_by_bucket[bucket]
        case_type_counts[case.case_type] = case_type_counts.get(case.case_type, 0) + 1
        if fastest_seconds < 0 or time_to_ack < fastest_seconds:
            fastest_seconds = time_to_ack
            fastest_case = case
        if time_to_ack > slowest_seconds:
            slowest_seconds = time_to_ack
            slowest_case = case

    def _payload(case: OperationalCase | None, seconds: int) -> dict[str, Any] | None:
        if case is None or case.acknowledged_at is None:
            return None
        return {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "severity": case.severity,
            "opened_at": case.opened_at.isoformat(),
            "acknowledged_at": case.acknowledged_at.isoformat(),
            "time_to_acknowledge_seconds": seconds,
        }

    return redact_secrets(
        {
            "business_id": business_id,
            "acknowledged_total": acknowledged_total,
            "by_acknowledgment_bucket": buckets,
            "by_acknowledgment_bucket_case_type": case_type_by_bucket,
            "fastest_acknowledged": _payload(fastest_case, fastest_seconds),
            "slowest_acknowledged": _payload(slowest_case, slowest_seconds),
        }
    )

def summarize_case_acknowledgment_latency_histogram_by_entity_kind(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Entity-kind-split deterministic histogram of time-to-acknowledge.

    Mirrors :func:`summarize_case_resolution_latency_histogram_by_entity_kind`
    but on the acknowledgment leg of the workflow, grouping each
    acknowledgment-latency bucket by ``entity_scope.kind`` (product/channel/
    business/conversation/etc.) so operator surfaces can spot which scopes
    dominate slow pickup — e.g. a healthy median that masks a per-product
    over-7d tail of stockout risks waiting on first-touch even when channel-
    level acknowledgment looks fine. Cases missing a ``kind`` are bucketed
    under ``"unknown"`` so totals never silently drop. Resolved cases are
    still counted (they were acknowledged at some point); only open-only
    cases without ``acknowledged_at`` are excluded. Strictly scoped per
    tenant.
    """

    buckets: dict[str, int] = {name: 0 for name, _ in _AGE_BUCKETS}
    entity_kind_by_bucket: dict[str, dict[str, int]] = {name: {} for name, _ in _AGE_BUCKETS}
    acknowledged_total = 0
    fastest_seconds = -1
    fastest_case: OperationalCase | None = None
    slowest_seconds = -1
    slowest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.acknowledged_at is None:
            continue
        acknowledged_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        acknowledged_at = case.acknowledged_at.astimezone(timezone.utc)
        time_to_ack = max(int((acknowledged_at - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(time_to_ack)
        buckets[bucket] += 1
        entity_kind = case.entity_scope.get("kind") or "unknown"
        entity_kind_counts = entity_kind_by_bucket[bucket]
        entity_kind_counts[entity_kind] = entity_kind_counts.get(entity_kind, 0) + 1
        if fastest_seconds < 0 or time_to_ack < fastest_seconds:
            fastest_seconds = time_to_ack
            fastest_case = case
        if time_to_ack > slowest_seconds:
            slowest_seconds = time_to_ack
            slowest_case = case

    def _payload(case: OperationalCase | None, seconds: int) -> dict[str, Any] | None:
        if case is None or case.acknowledged_at is None:
            return None
        return {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "severity": case.severity,
            "opened_at": case.opened_at.isoformat(),
            "acknowledged_at": case.acknowledged_at.isoformat(),
            "time_to_acknowledge_seconds": seconds,
        }

    return redact_secrets(
        {
            "business_id": business_id,
            "acknowledged_total": acknowledged_total,
            "by_acknowledgment_bucket": buckets,
            "by_acknowledgment_bucket_entity_kind": entity_kind_by_bucket,
            "fastest_acknowledged": _payload(fastest_case, fastest_seconds),
            "slowest_acknowledged": _payload(slowest_case, slowest_seconds),
        }
    )

def summarize_case_acknowledgment_latency_histogram_by_source_connector(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Source-connector-split deterministic histogram of time-to-acknowledge.

    Mirrors :func:`summarize_case_resolution_latency_histogram_by_source_connector`
    on the acknowledgment leg of the workflow, grouping each
    acknowledgment-latency bucket by source connector
    (tiendanube/google_sheets/csv/etc.) so operator surfaces can see which
    connectors dominate slow pickup — e.g. a healthy median that masks a
    Tiendanube over-7d tail of first-touch latency even when other connectors
    look fine. Each case is attributed to a single connector — the
    alphabetically-first source from its evidence snapshots, matching
    :func:`summarize_case_queue_aging_by_source_connector`,
    :func:`summarize_case_workflow_throughput_by_source_connector`, and
    :func:`summarize_case_resolution_latency_histogram_by_source_connector` —
    so the per-bucket totals always sum exactly to ``acknowledged_total``.
    Cases without any evidence source are bucketed under ``"unknown"`` so
    totals never silently drop. Resolved cases are still counted (they were
    acknowledged at some point); only open-only cases without
    ``acknowledged_at`` are excluded. Strictly scoped per tenant.
    """

    buckets: dict[str, int] = {name: 0 for name, _ in _AGE_BUCKETS}
    source_by_bucket: dict[str, dict[str, int]] = {name: {} for name, _ in _AGE_BUCKETS}
    acknowledged_total = 0
    fastest_seconds = -1
    fastest_case: OperationalCase | None = None
    slowest_seconds = -1
    slowest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.acknowledged_at is None:
            continue
        acknowledged_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        acknowledged_at = case.acknowledged_at.astimezone(timezone.utc)
        time_to_ack = max(int((acknowledged_at - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(time_to_ack)
        buckets[bucket] += 1
        sources = _source_connectors(case)
        primary_source = sources[0] if sources else "unknown"
        source_counts = source_by_bucket[bucket]
        source_counts[primary_source] = source_counts.get(primary_source, 0) + 1
        if fastest_seconds < 0 or time_to_ack < fastest_seconds:
            fastest_seconds = time_to_ack
            fastest_case = case
        if time_to_ack > slowest_seconds:
            slowest_seconds = time_to_ack
            slowest_case = case

    def _payload(case: OperationalCase | None, seconds: int) -> dict[str, Any] | None:
        if case is None or case.acknowledged_at is None:
            return None
        return {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "severity": case.severity,
            "opened_at": case.opened_at.isoformat(),
            "acknowledged_at": case.acknowledged_at.isoformat(),
            "time_to_acknowledge_seconds": seconds,
        }

    return redact_secrets(
        {
            "business_id": business_id,
            "acknowledged_total": acknowledged_total,
            "by_acknowledgment_bucket": buckets,
            "by_acknowledgment_bucket_source_connector": source_by_bucket,
            "fastest_acknowledged": _payload(fastest_case, fastest_seconds),
            "slowest_acknowledged": _payload(slowest_case, slowest_seconds),
        }
    )

def summarize_case_acknowledgment_latency_histogram_by_priority_bracket(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Priority-bracket-split deterministic histogram of time-to-acknowledge.

    Mirrors :func:`summarize_case_resolution_latency_histogram_by_priority_bracket`
    on the acknowledgment leg of the workflow, grouping each
    acknowledgment-latency bucket by deterministic priority bracket
    (``low`` for ``priority_score < 50``, ``medium`` for ``50..79``, ``high``
    for ``80..100``) derived from ``case.priority_score`` instead of source
    connector. Operator surfaces use it to spot when long-tail first-touch
    latency is concentrated in high-priority cases even though the overall
    median, case_type, entity_kind and source-connector distributions look
    healthy. Resolved cases are still counted (they were acknowledged at some
    point); only open-only cases without ``acknowledged_at`` are excluded.
    Strictly scoped per tenant.
    """

    buckets: dict[str, int] = {name: 0 for name, _ in _AGE_BUCKETS}
    bracket_by_bucket: dict[str, dict[str, int]] = {name: {} for name, _ in _AGE_BUCKETS}
    acknowledged_total = 0
    fastest_seconds = -1
    fastest_case: OperationalCase | None = None
    slowest_seconds = -1
    slowest_case: OperationalCase | None = None
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.acknowledged_at is None:
            continue
        acknowledged_total += 1
        opened_at = case.opened_at.astimezone(timezone.utc)
        acknowledged_at = case.acknowledged_at.astimezone(timezone.utc)
        time_to_ack = max(int((acknowledged_at - opened_at).total_seconds()), 0)
        bucket = _classify_age_bucket(time_to_ack)
        buckets[bucket] += 1
        bracket = _classify_priority_bracket(case.priority_score)
        bracket_counts = bracket_by_bucket[bucket]
        bracket_counts[bracket] = bracket_counts.get(bracket, 0) + 1
        if fastest_seconds < 0 or time_to_ack < fastest_seconds:
            fastest_seconds = time_to_ack
            fastest_case = case
        if time_to_ack > slowest_seconds:
            slowest_seconds = time_to_ack
            slowest_case = case

    def _payload(case: OperationalCase | None, seconds: int) -> dict[str, Any] | None:
        if case is None or case.acknowledged_at is None:
            return None
        return {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "severity": case.severity,
            "opened_at": case.opened_at.isoformat(),
            "acknowledged_at": case.acknowledged_at.isoformat(),
            "time_to_acknowledge_seconds": seconds,
        }

    return redact_secrets(
        {
            "business_id": business_id,
            "acknowledged_total": acknowledged_total,
            "by_acknowledgment_bucket": buckets,
            "by_acknowledgment_bucket_priority_bracket": bracket_by_bucket,
            "fastest_acknowledged": _payload(fastest_case, fastest_seconds),
            "slowest_acknowledged": _payload(slowest_case, slowest_seconds),
        }
    )

__all__ = [name for name in globals() if not name.startswith("__")]

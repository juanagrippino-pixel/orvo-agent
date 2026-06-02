from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403


def summarize_case_workflow_throughput(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Deterministic lifecycle latency aggregates for cases in a business.

    Computes time-to-acknowledge (opened_at -> acknowledged_at) and
    time-to-resolve (opened_at -> resolved_at) in whole seconds for cases
    that have reached those lifecycle states. Open-only cases contribute to
    ``total`` but not to the latency aggregates. Strictly scoped per tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    ack_latencies: list[int] = []
    resolve_latencies: list[int] = []
    for case in cases:
        if case.acknowledged_at is not None:
            ack_latencies.append(int((case.acknowledged_at - case.opened_at).total_seconds()))
        if case.resolved_at is not None:
            resolve_latencies.append(int((case.resolved_at - case.opened_at).total_seconds()))
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "acknowledged_count": len(ack_latencies),
            "resolved_count": len(resolve_latencies),
            "time_to_acknowledge_seconds": _latency_summary(ack_latencies),
            "time_to_resolve_seconds": _latency_summary(resolve_latencies),
        }
    )

def summarize_case_workflow_throughput_by_severity(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Severity-split lifecycle latency aggregates for cases in a business.

    Mirrors :func:`summarize_case_workflow_throughput` but groups every count
    and latency aggregate by case severity (info/warning/critical). Operator
    surfaces use this to spot SLA pressure where a few slow info-level cases
    would otherwise mask fast acknowledgment on criticals. Strictly scoped
    per tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    totals_by_severity: dict[str, int] = {}
    ack_by_severity: dict[str, int] = {}
    resolve_by_severity: dict[str, int] = {}
    ack_latencies_by_severity: dict[str, list[int]] = {}
    resolve_latencies_by_severity: dict[str, list[int]] = {}
    for case in cases:
        severity = case.severity
        totals_by_severity[severity] = totals_by_severity.get(severity, 0) + 1
        if case.acknowledged_at is not None:
            ack_latency = int((case.acknowledged_at - case.opened_at).total_seconds())
            ack_by_severity[severity] = ack_by_severity.get(severity, 0) + 1
            ack_latencies_by_severity.setdefault(severity, []).append(ack_latency)
        if case.resolved_at is not None:
            resolve_latency = int((case.resolved_at - case.opened_at).total_seconds())
            resolve_by_severity[severity] = resolve_by_severity.get(severity, 0) + 1
            resolve_latencies_by_severity.setdefault(severity, []).append(resolve_latency)
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "totals_by_severity": totals_by_severity,
            "acknowledged_by_severity": ack_by_severity,
            "resolved_by_severity": resolve_by_severity,
            "time_to_acknowledge_seconds_by_severity": {
                severity: _latency_summary(values)
                for severity, values in ack_latencies_by_severity.items()
            },
            "time_to_resolve_seconds_by_severity": {
                severity: _latency_summary(values)
                for severity, values in resolve_latencies_by_severity.items()
            },
        }
    )

def summarize_case_workflow_throughput_by_case_type(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Case-type-split lifecycle latency aggregates for cases in a business.

    Mirrors :func:`summarize_case_workflow_throughput` but groups every count
    and latency aggregate by case type (sales_drop/stockout_risk/etc.). Lets
    operator surfaces spot which case families are draining acknowledgment or
    resolution time even when severity counts look balanced. Strictly scoped
    per tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    totals_by_case_type: dict[str, int] = {}
    ack_by_case_type: dict[str, int] = {}
    resolve_by_case_type: dict[str, int] = {}
    ack_latencies_by_case_type: dict[str, list[int]] = {}
    resolve_latencies_by_case_type: dict[str, list[int]] = {}
    for case in cases:
        case_type = case.case_type
        totals_by_case_type[case_type] = totals_by_case_type.get(case_type, 0) + 1
        if case.acknowledged_at is not None:
            ack_latency = int((case.acknowledged_at - case.opened_at).total_seconds())
            ack_by_case_type[case_type] = ack_by_case_type.get(case_type, 0) + 1
            ack_latencies_by_case_type.setdefault(case_type, []).append(ack_latency)
        if case.resolved_at is not None:
            resolve_latency = int((case.resolved_at - case.opened_at).total_seconds())
            resolve_by_case_type[case_type] = resolve_by_case_type.get(case_type, 0) + 1
            resolve_latencies_by_case_type.setdefault(case_type, []).append(resolve_latency)
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "totals_by_case_type": totals_by_case_type,
            "acknowledged_by_case_type": ack_by_case_type,
            "resolved_by_case_type": resolve_by_case_type,
            "time_to_acknowledge_seconds_by_case_type": {
                case_type: _latency_summary(values)
                for case_type, values in ack_latencies_by_case_type.items()
            },
            "time_to_resolve_seconds_by_case_type": {
                case_type: _latency_summary(values)
                for case_type, values in resolve_latencies_by_case_type.items()
            },
        }
    )

def summarize_case_workflow_throughput_by_entity_kind(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Entity-kind-split lifecycle latency aggregates for cases in a business.

    Mirrors :func:`summarize_case_workflow_throughput` but groups every count
    and latency aggregate by ``entity_scope.kind`` (product/channel/business/etc.).
    Operator surfaces use this to spot which scopes are draining acknowledgment
    or resolution time — for example, a slow per-product backlog hidden inside
    healthy channel-level numbers. Cases missing a ``kind`` are bucketed under
    ``"unknown"`` so totals never silently drop. Strictly scoped per tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    totals_by_entity_kind: dict[str, int] = {}
    ack_by_entity_kind: dict[str, int] = {}
    resolve_by_entity_kind: dict[str, int] = {}
    ack_latencies_by_entity_kind: dict[str, list[int]] = {}
    resolve_latencies_by_entity_kind: dict[str, list[int]] = {}
    for case in cases:
        entity_kind = case.entity_scope.get("kind") or "unknown"
        totals_by_entity_kind[entity_kind] = totals_by_entity_kind.get(entity_kind, 0) + 1
        if case.acknowledged_at is not None:
            ack_latency = int((case.acknowledged_at - case.opened_at).total_seconds())
            ack_by_entity_kind[entity_kind] = ack_by_entity_kind.get(entity_kind, 0) + 1
            ack_latencies_by_entity_kind.setdefault(entity_kind, []).append(ack_latency)
        if case.resolved_at is not None:
            resolve_latency = int((case.resolved_at - case.opened_at).total_seconds())
            resolve_by_entity_kind[entity_kind] = resolve_by_entity_kind.get(entity_kind, 0) + 1
            resolve_latencies_by_entity_kind.setdefault(entity_kind, []).append(resolve_latency)
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "totals_by_entity_kind": totals_by_entity_kind,
            "acknowledged_by_entity_kind": ack_by_entity_kind,
            "resolved_by_entity_kind": resolve_by_entity_kind,
            "time_to_acknowledge_seconds_by_entity_kind": {
                entity_kind: _latency_summary(values)
                for entity_kind, values in ack_latencies_by_entity_kind.items()
            },
            "time_to_resolve_seconds_by_entity_kind": {
                entity_kind: _latency_summary(values)
                for entity_kind, values in resolve_latencies_by_entity_kind.items()
            },
        }
    )

def summarize_case_workflow_throughput_by_source_connector(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Source-connector-split lifecycle latency aggregates for cases in a business.

    Mirrors :func:`summarize_case_workflow_throughput` but groups every count
    and latency aggregate by source connector (tiendanube/google_sheets/csv/
    etc.). Operator surfaces use this to spot which connectors' cases drag
    acknowledgment or resolution time — a stuck connector or noisy data source
    often shows up as a slow per-source bucket even when severity and case_type
    counts look healthy. Each case is attributed to a single connector — the
    alphabetically-first source from its evidence snapshots — so the per-bucket
    totals always sum exactly to ``total``. Cases without any evidence source
    are bucketed under ``"unknown"`` so totals never silently drop. Strictly
    scoped per tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    totals_by_source: dict[str, int] = {}
    ack_by_source: dict[str, int] = {}
    resolve_by_source: dict[str, int] = {}
    ack_latencies_by_source: dict[str, list[int]] = {}
    resolve_latencies_by_source: dict[str, list[int]] = {}
    for case in cases:
        sources = _source_connectors(case)
        # _source_connectors returns sorted unique sources; pick the first as
        # the case's primary connector so each case contributes to exactly one
        # bucket and per-bucket counts sum to ``total``.
        primary_source = sources[0] if sources else "unknown"
        totals_by_source[primary_source] = totals_by_source.get(primary_source, 0) + 1
        if case.acknowledged_at is not None:
            ack_latency = int((case.acknowledged_at - case.opened_at).total_seconds())
            ack_by_source[primary_source] = ack_by_source.get(primary_source, 0) + 1
            ack_latencies_by_source.setdefault(primary_source, []).append(ack_latency)
        if case.resolved_at is not None:
            resolve_latency = int((case.resolved_at - case.opened_at).total_seconds())
            resolve_by_source[primary_source] = resolve_by_source.get(primary_source, 0) + 1
            resolve_latencies_by_source.setdefault(primary_source, []).append(resolve_latency)
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "totals_by_source_connector": totals_by_source,
            "acknowledged_by_source_connector": ack_by_source,
            "resolved_by_source_connector": resolve_by_source,
            "time_to_acknowledge_seconds_by_source_connector": {
                source: _latency_summary(values)
                for source, values in ack_latencies_by_source.items()
            },
            "time_to_resolve_seconds_by_source_connector": {
                source: _latency_summary(values)
                for source, values in resolve_latencies_by_source.items()
            },
        }
    )

def summarize_case_workflow_throughput_by_priority_bracket(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Priority-bracket-split lifecycle latency aggregates for cases in a business.

    Mirrors :func:`summarize_case_workflow_throughput_by_source_connector` but
    groups every count and latency aggregate by deterministic priority bracket
    (low / medium / high) derived from ``case.priority_score`` via
    :func:`_classify_priority_bracket`. Operator surfaces use this to spot when
    high-priority cases drag acknowledgment or resolution time even though
    severity, case_type, entity_kind and source-connector aggregates look
    healthy. Strictly scoped per tenant.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    totals_by_bracket: dict[str, int] = {}
    ack_by_bracket: dict[str, int] = {}
    resolve_by_bracket: dict[str, int] = {}
    ack_latencies_by_bracket: dict[str, list[int]] = {}
    resolve_latencies_by_bracket: dict[str, list[int]] = {}
    for case in cases:
        bracket = _classify_priority_bracket(case.priority_score)
        totals_by_bracket[bracket] = totals_by_bracket.get(bracket, 0) + 1
        if case.acknowledged_at is not None:
            ack_latency = int((case.acknowledged_at - case.opened_at).total_seconds())
            ack_by_bracket[bracket] = ack_by_bracket.get(bracket, 0) + 1
            ack_latencies_by_bracket.setdefault(bracket, []).append(ack_latency)
        if case.resolved_at is not None:
            resolve_latency = int((case.resolved_at - case.opened_at).total_seconds())
            resolve_by_bracket[bracket] = resolve_by_bracket.get(bracket, 0) + 1
            resolve_latencies_by_bracket.setdefault(bracket, []).append(resolve_latency)
    return redact_secrets(
        {
            "business_id": business_id,
            "total": len(cases),
            "totals_by_priority_bracket": totals_by_bracket,
            "acknowledged_by_priority_bracket": ack_by_bracket,
            "resolved_by_priority_bracket": resolve_by_bracket,
            "time_to_acknowledge_seconds_by_priority_bracket": {
                bracket: _latency_summary(values)
                for bracket, values in ack_latencies_by_bracket.items()
            },
            "time_to_resolve_seconds_by_priority_bracket": {
                bracket: _latency_summary(values)
                for bracket, values in resolve_latencies_by_bracket.items()
            },
        }
    )

__all__ = [name for name in globals() if not name.startswith("__")]

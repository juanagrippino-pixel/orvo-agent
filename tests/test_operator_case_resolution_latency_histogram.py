"""Tests for the deterministic resolution-latency histogram projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import summarize_case_resolution_latency_histogram


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-res-1",
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def _empty_buckets() -> dict[str, int]:
    return {"under_1h": 0, "under_6h": 0, "under_24h": 0, "under_7d": 0, "over_7d": 0}


def _resolve(
    store: InMemoryOperationalCaseStore,
    *,
    detection: OperationalCaseDetection,
    opened_at: datetime,
    resolved_at: datetime,
) -> str:
    case = store.upsert_detection(detection, detected_at=opened_at)
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=opened_at + (resolved_at - opened_at) / 2,
    )
    store.transition_case(
        case.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved in test fixture",
        transitioned_at=resolved_at,
    )
    return case.case_id


def test_summarize_case_resolution_latency_histogram_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_resolution_latency_histogram(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "resolved_total": 0,
        "by_resolution_bucket": _empty_buckets(),
        "by_resolution_bucket_severity": {bucket: {} for bucket in _empty_buckets()},
        "fastest_resolved": None,
        "slowest_resolved": None,
    }


def test_summarize_case_resolution_latency_histogram_buckets_resolved_cases_by_time_to_resolve():
    store = InMemoryOperationalCaseStore()

    schedule = [
        ("a", "stockout_risk", "stockout_risk/business/monitored/commerce.inventory/daily", "critical", timedelta(minutes=30)),     # under_1h
        ("b", "sales_drop", "sales_drop/channel/all/commerce.revenue/daily", "warning", timedelta(hours=3)),                          # under_6h
        ("c", "sales_drop", "sales_drop/channel/meta_ads/commerce.revenue/daily", "warning", timedelta(hours=10)),                    # under_24h
        ("d", "unanswered_conversations", "unanswered_conversations/channel/whatsapp/support.conversations/daily", "warning", timedelta(days=2)),  # under_7d
        ("e", "data_stale", "data_stale/business/monitored/observability.feeds/daily", "info", timedelta(days=10)),                   # over_7d
    ]
    for run_id, case_type, dedupe_suffix, severity, ttr in schedule:
        opened_at = NOW - timedelta(days=30)
        _resolve(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity=severity,
                priority=70,
                run_id=f"run-{run_id}",
            ),
            opened_at=opened_at,
            resolved_at=opened_at + ttr,
        )

    result = summarize_case_resolution_latency_histogram(store, business_id="artemea")

    assert result["resolved_total"] == 5
    assert result["by_resolution_bucket"] == {
        "under_1h": 1,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 1,
        "over_7d": 1,
    }
    assert result["by_resolution_bucket_severity"] == {
        "under_1h": {"critical": 1},
        "under_6h": {"warning": 1},
        "under_24h": {"warning": 1},
        "under_7d": {"warning": 1},
        "over_7d": {"info": 1},
    }
    fastest = result["fastest_resolved"]
    slowest = result["slowest_resolved"]
    assert fastest is not None and slowest is not None
    assert fastest["time_to_resolve_seconds"] == int(timedelta(minutes=30).total_seconds())
    assert fastest["case_type"] == "stockout_risk"
    assert fastest["severity"] == "critical"
    assert isinstance(fastest["case_id"], str) and fastest["case_id"]
    assert fastest["opened_at"].endswith("+00:00")
    assert fastest["resolved_at"].endswith("+00:00")
    assert slowest["time_to_resolve_seconds"] == int(timedelta(days=10).total_seconds())
    assert slowest["case_type"] == "data_stale"
    assert slowest["severity"] == "info"


def test_summarize_case_resolution_latency_histogram_excludes_open_and_acknowledged_cases():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=3)

    # Open-only case.
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open"),
        detected_at=opened_at,
    )

    # Acknowledged-only case.
    ack = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-ack",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        ack.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=opened_at + timedelta(hours=1),
    )

    # Resolved case — 4h time-to-resolve -> under_6h.
    resolved_id = _resolve(
        store,
        detection=_detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/support.conversations/daily",
            severity="warning",
            priority=70,
            run_id="run-resolved",
        ),
        opened_at=opened_at,
        resolved_at=opened_at + timedelta(hours=4),
    )

    result = summarize_case_resolution_latency_histogram(store, business_id="artemea")

    assert result["resolved_total"] == 1
    assert result["by_resolution_bucket"]["under_6h"] == 1
    assert result["by_resolution_bucket"]["under_1h"] == 0
    assert result["fastest_resolved"]["case_id"] == resolved_id
    assert result["slowest_resolved"]["case_id"] == resolved_id


def test_summarize_case_resolution_latency_histogram_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=5)

    _resolve(
        store,
        detection=_detection(business_id="artemea", run_id="run-a"),
        opened_at=opened_at,
        resolved_at=opened_at + timedelta(hours=2),
    )
    _resolve(
        store,
        detection=_detection(business_id="other-shop", run_id="run-other"),
        opened_at=opened_at,
        resolved_at=opened_at + timedelta(days=8),
    )

    result = summarize_case_resolution_latency_histogram(store, business_id="artemea")

    assert result["resolved_total"] == 1
    assert result["by_resolution_bucket"]["under_6h"] == 1
    assert result["by_resolution_bucket"]["over_7d"] == 0
    assert result["fastest_resolved"]["time_to_resolve_seconds"] == int(timedelta(hours=2).total_seconds())
    assert result["slowest_resolved"]["time_to_resolve_seconds"] == int(timedelta(hours=2).total_seconds())


def test_summarize_case_resolution_latency_histogram_groups_multiple_cases_per_bucket_by_severity():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    schedule = [
        ("a1", "stockout_risk", "stockout_risk/business/monitored/commerce.inventory/daily", "critical", timedelta(hours=2)),
        ("a2", "sales_drop", "sales_drop/channel/all/commerce.revenue/daily", "warning", timedelta(hours=4)),
        ("a3", "sales_drop", "sales_drop/channel/meta_ads/commerce.revenue/daily", "warning", timedelta(hours=5)),
        ("a4", "data_stale", "data_stale/business/monitored/observability.feeds/daily", "info", timedelta(days=8)),
    ]
    for run_id, case_type, dedupe_suffix, severity, ttr in schedule:
        _resolve(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity=severity,
                priority=70,
                run_id=f"run-{run_id}",
            ),
            opened_at=opened_at,
            resolved_at=opened_at + ttr,
        )

    result = summarize_case_resolution_latency_histogram(store, business_id="artemea")

    assert result["resolved_total"] == 4
    assert result["by_resolution_bucket"] == {
        "under_1h": 0,
        "under_6h": 3,
        "under_24h": 0,
        "under_7d": 0,
        "over_7d": 1,
    }
    assert result["by_resolution_bucket_severity"]["under_6h"] == {
        "critical": 1,
        "warning": 2,
    }
    assert result["by_resolution_bucket_severity"]["over_7d"] == {"info": 1}

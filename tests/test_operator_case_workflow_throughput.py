"""Tests for the deterministic case workflow throughput projection."""

from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import summarize_case_workflow_throughput


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-throughput-1",
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


def test_summarize_case_workflow_throughput_returns_empty_summary_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_workflow_throughput(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "total": 0,
        "acknowledged_count": 0,
        "resolved_count": 0,
        "time_to_acknowledge_seconds": {},
        "time_to_resolve_seconds": {},
    }


def test_summarize_case_workflow_throughput_aggregates_latencies_from_lifecycle_timestamps():
    store = InMemoryOperationalCaseStore()
    # Case A: opened 08:00, acknowledged 11:00, resolved 12:00.
    a = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/monitored/commerce.inventory/daily",
            run_id="run-a",
        ),
        detected_at=_utc(8),
    )
    store.transition_case(
        a.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(11),
    )
    store.transition_case(
        a.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved in test fixture",
        transitioned_at=_utc(12),
    )
    # Case B: opened 08:00, acknowledged 09:00 only.
    b = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-b",
        ),
        detected_at=_utc(8),
    )
    store.transition_case(
        b.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(9),
    )
    # Case C: opened 08:00 and still open — should not contribute to latencies.
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/meta_ads/commerce.revenue/daily",
            severity="warning",
            priority=65,
            run_id="run-c",
        ),
        detected_at=_utc(8),
    )

    result = summarize_case_workflow_throughput(store, business_id="artemea")

    assert result["business_id"] == "artemea"
    assert result["total"] == 3
    assert result["acknowledged_count"] == 2
    assert result["resolved_count"] == 1
    # Case A ack latency = 3h = 10800s, Case B ack latency = 1h = 3600s.
    assert result["time_to_acknowledge_seconds"] == {
        "min": 3600,
        "max": 10800,
        "avg": 7200,
        "median": 7200,
    }
    # Case A resolve latency = 4h = 14400s.
    assert result["time_to_resolve_seconds"] == {
        "min": 14400,
        "max": 14400,
        "avg": 14400,
        "median": 14400,
    }


def test_summarize_case_workflow_throughput_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    a = store.upsert_detection(_detection(business_id="artemea", run_id="run-a"), detected_at=_utc(8))
    store.transition_case(
        a.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(10),
    )
    other = store.upsert_detection(
        _detection(business_id="other-shop", run_id="run-other"),
        detected_at=_utc(8),
    )
    store.transition_case(
        other.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(20),
    )
    store.transition_case(
        other.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved in test fixture",
        transitioned_at=_utc(22),
    )

    result = summarize_case_workflow_throughput(store, business_id="artemea")

    assert result["total"] == 1
    assert result["acknowledged_count"] == 1
    assert result["resolved_count"] == 0
    # Latencies must come from artemea only (2h), not the other-shop 12h ack latency.
    assert result["time_to_acknowledge_seconds"] == {
        "min": 7200,
        "max": 7200,
        "avg": 7200,
        "median": 7200,
    }
    assert result["time_to_resolve_seconds"] == {}


def test_summarize_case_workflow_throughput_median_uses_integer_midpoint_for_even_counts():
    store = InMemoryOperationalCaseStore()
    # Four acknowledged cases with latencies 1h, 2h, 3h, 5h (in seconds: 3600/7200/10800/18000).
    schedule = [
        ("a", "stockout_risk/business/monitored/commerce.inventory/daily", 1),
        ("b", "sales_drop/channel/all/commerce.revenue/daily", 2),
        ("c", "sales_drop/channel/meta_ads/commerce.revenue/daily", 3),
        ("d", "unanswered_conversations/channel/whatsapp/support.conversations/daily", 5),
    ]
    case_types = {
        "stockout_risk/business/monitored/commerce.inventory/daily": "stockout_risk",
        "sales_drop/channel/all/commerce.revenue/daily": "sales_drop",
        "sales_drop/channel/meta_ads/commerce.revenue/daily": "sales_drop",
        "unanswered_conversations/channel/whatsapp/support.conversations/daily": "unanswered_conversations",
    }
    for run_id, dedupe_suffix, ack_hour_offset in schedule:
        case = store.upsert_detection(
            _detection(
                case_type=case_types[dedupe_suffix],  # type: ignore[arg-type]
                dedupe_suffix=dedupe_suffix,
                severity="warning",
                priority=70,
                run_id=f"run-{run_id}",
            ),
            detected_at=_utc(8),
        )
        store.transition_case(
            case.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="operator@example.com",
            transitioned_at=_utc(8 + ack_hour_offset),
        )

    result = summarize_case_workflow_throughput(store, business_id="artemea")

    # Sorted latencies: [3600, 7200, 10800, 18000].
    # avg = 9900, median = (7200 + 10800) // 2 = 9000.
    assert result["acknowledged_count"] == 4
    assert result["time_to_acknowledge_seconds"] == {
        "min": 3600,
        "max": 18000,
        "avg": 9900,
        "median": 9000,
    }

"""Tests for the case-type-split handling-latency histogram projection.

Handling latency = ``resolved_at - acknowledged_at`` (operator working
time). This projection mirrors
:func:`summarize_case_handling_latency_histogram` but groups each bucket
by case type so operator surfaces can see which case families dominate
slow hands-on resolution tails even when the overall median looks fine.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    summarize_case_handling_latency_histogram_by_case_type,
)


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-handle-ct-1",
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


def _handle(
    store: InMemoryOperationalCaseStore,
    *,
    detection: OperationalCaseDetection,
    opened_at: datetime,
    acknowledged_at: datetime,
    resolved_at: datetime,
) -> str:
    case = store.upsert_detection(detection, detected_at=opened_at)
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=acknowledged_at,
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


def test_handling_latency_histogram_by_case_type_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_handling_latency_histogram_by_case_type(
        store, business_id="artemea"
    )

    assert result == {
        "business_id": "artemea",
        "handled_total": 0,
        "by_handling_bucket": _empty_buckets(),
        "by_handling_bucket_case_type": {bucket: {} for bucket in _empty_buckets()},
        "fastest_handled": None,
        "slowest_handled": None,
    }


def test_handling_latency_histogram_by_case_type_buckets_by_case_type():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    # (run_id, case_type, dedupe_suffix, severity, ack_delay, resolve_delay)
    schedule = [
        (
            "a",
            "stockout_risk",
            "stockout_risk/product/sku-a/commerce.inventory/daily",
            "critical",
            timedelta(hours=1),
            timedelta(hours=1, minutes=30),  # handling = 30m -> under_1h
        ),
        (
            "b",
            "sales_drop",
            "sales_drop/channel/all/commerce.revenue/daily",
            "warning",
            timedelta(hours=2),
            timedelta(hours=6),  # handling = 4h -> under_6h
        ),
        (
            "c",
            "sales_drop",
            "sales_drop/channel/meta_ads/commerce.revenue/daily",
            "warning",
            timedelta(hours=1),
            timedelta(hours=11),  # handling = 10h -> under_24h
        ),
        (
            "d",
            "unanswered_conversations",
            "unanswered_conversations/conversation/wa-99/support.conversations/daily",
            "info",
            timedelta(hours=1),
            timedelta(days=2, hours=1),  # handling = 2d -> under_7d
        ),
        (
            "e",
            "data_stale",
            "data_stale/business/monitored/observability.feeds/daily",
            "info",
            timedelta(hours=1),
            timedelta(days=10, hours=1),  # handling = 10d -> over_7d
        ),
    ]
    for run_id, case_type, dedupe_suffix, severity, ack_delay, resolve_delay in schedule:
        _handle(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity=severity,
                run_id=f"run-{run_id}",
            ),
            opened_at=opened_at,
            acknowledged_at=opened_at + ack_delay,
            resolved_at=opened_at + resolve_delay,
        )

    result = summarize_case_handling_latency_histogram_by_case_type(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 5
    assert result["by_handling_bucket"] == {
        "under_1h": 1,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 1,
        "over_7d": 1,
    }
    assert result["by_handling_bucket_case_type"] == {
        "under_1h": {"stockout_risk": 1},
        "under_6h": {"sales_drop": 1},
        "under_24h": {"sales_drop": 1},
        "under_7d": {"unanswered_conversations": 1},
        "over_7d": {"data_stale": 1},
    }
    fastest = result["fastest_handled"]
    slowest = result["slowest_handled"]
    assert fastest is not None and slowest is not None
    assert fastest["time_to_handle_seconds"] == int(timedelta(minutes=30).total_seconds())
    assert fastest["case_type"] == "stockout_risk"
    assert slowest["time_to_handle_seconds"] == int(timedelta(days=10).total_seconds())
    assert slowest["case_type"] == "data_stale"


def test_handling_latency_histogram_by_case_type_excludes_open_and_acknowledged_only_cases():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=3)

    # Open-only -> excluded.
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open"),
        detected_at=opened_at,
    )

    # Acknowledged-only (not resolved) -> excluded: handling time isn't finalised.
    ack_only = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            run_id="run-ack-only",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        ack_only.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=opened_at + timedelta(hours=1),
    )

    # Fully handled case -> counted, handling = 3h -> under_6h.
    handled_id = _handle(
        store,
        detection=_detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/conversation/wa-99/support.conversations/daily",
            severity="info",
            run_id="run-handled",
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=1),
        resolved_at=opened_at + timedelta(hours=4),
    )

    result = summarize_case_handling_latency_histogram_by_case_type(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_6h"] == 1
    assert result["by_handling_bucket_case_type"]["under_6h"] == {
        "unanswered_conversations": 1,
    }
    assert result["fastest_handled"]["case_id"] == handled_id
    assert result["slowest_handled"]["case_id"] == handled_id


def test_handling_latency_histogram_by_case_type_groups_multiple_cases_per_bucket():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    schedule = [
        (
            "a1",
            "stockout_risk",
            "stockout_risk/product/sku-a/commerce.inventory/daily",
            "critical",
            timedelta(hours=2),
            timedelta(hours=4),  # handling = 2h -> under_6h
        ),
        (
            "a2",
            "sales_drop",
            "sales_drop/channel/all/commerce.revenue/daily",
            "warning",
            timedelta(hours=1),
            timedelta(hours=5),  # handling = 4h -> under_6h
        ),
        (
            "a3",
            "sales_drop",
            "sales_drop/channel/meta_ads/commerce.revenue/daily",
            "warning",
            timedelta(hours=2),
            timedelta(hours=7),  # handling = 5h -> under_6h
        ),
        (
            "a4",
            "data_stale",
            "data_stale/business/monitored/observability.feeds/daily",
            "info",
            timedelta(hours=1),
            timedelta(days=8, hours=1),  # handling = 8d -> over_7d
        ),
    ]
    for run_id, case_type, dedupe_suffix, severity, ack_delay, resolve_delay in schedule:
        _handle(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity=severity,
                run_id=f"run-{run_id}",
            ),
            opened_at=opened_at,
            acknowledged_at=opened_at + ack_delay,
            resolved_at=opened_at + resolve_delay,
        )

    result = summarize_case_handling_latency_histogram_by_case_type(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 4
    assert result["by_handling_bucket"] == {
        "under_1h": 0,
        "under_6h": 3,
        "under_24h": 0,
        "under_7d": 0,
        "over_7d": 1,
    }
    assert result["by_handling_bucket_case_type"]["under_6h"] == {
        "stockout_risk": 1,
        "sales_drop": 2,
    }
    assert result["by_handling_bucket_case_type"]["over_7d"] == {"data_stale": 1}


def test_handling_latency_histogram_by_case_type_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=5)

    _handle(
        store,
        detection=_detection(business_id="artemea", run_id="run-a"),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=1),
        resolved_at=opened_at + timedelta(hours=3),  # handling = 2h -> under_6h
    )
    _handle(
        store,
        detection=_detection(
            business_id="other-shop",
            case_type="data_stale",
            dedupe_suffix="data_stale/business/monitored/observability.feeds/daily",
            severity="info",
            run_id="run-other",
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=1),
        resolved_at=opened_at + timedelta(days=9),  # handling > 7d -> over_7d
    )

    result = summarize_case_handling_latency_histogram_by_case_type(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_6h"] == 1
    assert result["by_handling_bucket"]["over_7d"] == 0
    assert result["by_handling_bucket_case_type"]["under_6h"] == {"stockout_risk": 1}
    assert "data_stale" not in result["by_handling_bucket_case_type"]["over_7d"]


def test_handling_latency_histogram_by_case_type_clamps_non_positive_handling_to_zero():
    # Defensive: when resolved_at == acknowledged_at the handling time is zero
    # and must still land in under_1h under the right case type.
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(hours=2)
    acknowledged_at = opened_at + timedelta(hours=1)

    _handle(
        store,
        detection=_detection(case_type="stockout_risk", run_id="run-zero"),
        opened_at=opened_at,
        acknowledged_at=acknowledged_at,
        resolved_at=acknowledged_at,
    )

    result = summarize_case_handling_latency_histogram_by_case_type(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_1h"] == 1
    assert result["by_handling_bucket_case_type"]["under_1h"] == {"stockout_risk": 1}
    assert result["fastest_handled"]["time_to_handle_seconds"] == 0
    assert result["slowest_handled"]["time_to_handle_seconds"] == 0

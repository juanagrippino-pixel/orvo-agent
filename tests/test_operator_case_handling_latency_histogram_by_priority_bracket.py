"""Tests for the priority-bracket-split handling-latency histogram projection.

Handling latency = ``resolved_at - acknowledged_at`` (hands-on leg, after
the operator has picked the case up). This projection mirrors
:func:`summarize_case_handling_latency_histogram` but groups each bucket
by deterministic priority bracket (low / medium / high) derived from
``case.priority_score`` instead of severity. Operator surfaces use it to
spot when long-tail hands-on resolution time is concentrated in
high-priority cases even though the overall median, case_type,
entity_kind and source-connector distributions look healthy.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    summarize_case_handling_latency_histogram_by_priority_bracket,
)


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-handle-pb-1",
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
        transitioned_at=resolved_at,
    )
    return case.case_id


def test_handling_latency_histogram_by_priority_bracket_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_handling_latency_histogram_by_priority_bracket(
        store, business_id="artemea"
    )

    assert result == {
        "business_id": "artemea",
        "handled_total": 0,
        "by_handling_bucket": _empty_buckets(),
        "by_handling_bucket_priority_bracket": {
            bucket: {} for bucket in _empty_buckets()
        },
        "fastest_handled": None,
        "slowest_handled": None,
    }


def test_handling_latency_histogram_by_priority_bracket_buckets_by_priority_bracket():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)
    acknowledged_at = opened_at + timedelta(minutes=5)

    # (run_id, case_type, dedupe_suffix, priority_score, tth, expected_bracket)
    schedule = [
        (
            "a",
            "stockout_risk",
            "stockout_risk/product/sku-a/commerce.inventory/daily",
            95,  # high
            timedelta(minutes=30),  # under_1h
        ),
        (
            "b",
            "sales_drop",
            "sales_drop/channel/all/commerce.revenue/daily",
            65,  # medium
            timedelta(hours=3),  # under_6h
        ),
        (
            "c",
            "sales_drop",
            "sales_drop/channel/meta_ads/commerce.revenue/daily",
            55,  # medium
            timedelta(hours=10),  # under_24h
        ),
        (
            "d",
            "unanswered_conversations",
            "unanswered_conversations/conversation/wa-99/support.conversations/daily",
            30,  # low
            timedelta(days=2),  # under_7d
        ),
        (
            "e",
            "data_stale",
            "data_stale/business/monitored/observability.feeds/daily",
            10,  # low
            timedelta(days=10),  # over_7d
        ),
    ]
    for run_id, case_type, dedupe_suffix, priority, tth in schedule:
        _handle(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity="warning",
                priority=priority,
                run_id=f"run-{run_id}",
            ),
            opened_at=opened_at,
            acknowledged_at=acknowledged_at,
            resolved_at=acknowledged_at + tth,
        )

    result = summarize_case_handling_latency_histogram_by_priority_bracket(
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
    assert result["by_handling_bucket_priority_bracket"] == {
        "under_1h": {"high": 1},
        "under_6h": {"medium": 1},
        "under_24h": {"medium": 1},
        "under_7d": {"low": 1},
        "over_7d": {"low": 1},
    }
    fastest = result["fastest_handled"]
    slowest = result["slowest_handled"]
    assert fastest is not None and slowest is not None
    assert fastest["time_to_handle_seconds"] == int(timedelta(minutes=30).total_seconds())
    assert fastest["case_type"] == "stockout_risk"
    assert slowest["time_to_handle_seconds"] == int(timedelta(days=10).total_seconds())
    assert slowest["case_type"] == "data_stale"


def test_handling_latency_histogram_by_priority_bracket_buckets_score_boundaries():
    # Boundary-condition cases that pin the bracket cutoffs:
    #   score < 50           -> "low"
    #   50 <= score < 80     -> "medium"
    #   80 <= score <= 100   -> "high"
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)
    acknowledged_at = opened_at + timedelta(minutes=5)

    # (run_id, dedupe_suffix, priority, expected_bracket)
    schedule = [
        ("low-top", "stockout_risk/product/low-top/commerce.inventory/daily", 49, "low"),
        ("med-low", "stockout_risk/product/med-low/commerce.inventory/daily", 50, "medium"),
        ("med-top", "stockout_risk/product/med-top/commerce.inventory/daily", 79, "medium"),
        ("high-low", "stockout_risk/product/high-low/commerce.inventory/daily", 80, "high"),
        ("high-top", "stockout_risk/product/high-top/commerce.inventory/daily", 100, "high"),
        ("low-zero", "stockout_risk/product/low-zero/commerce.inventory/daily", 0, "low"),
    ]
    for run_id, dedupe_suffix, priority, _expected in schedule:
        _handle(
            store,
            detection=_detection(
                dedupe_suffix=dedupe_suffix,
                severity="warning",
                priority=priority,
                run_id=f"run-{run_id}",
            ),
            opened_at=opened_at,
            acknowledged_at=acknowledged_at,
            resolved_at=acknowledged_at + timedelta(hours=2),  # all in under_6h
        )

    result = summarize_case_handling_latency_histogram_by_priority_bracket(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 6
    assert result["by_handling_bucket"]["under_6h"] == 6
    assert result["by_handling_bucket_priority_bracket"]["under_6h"] == {
        "low": 2,
        "medium": 2,
        "high": 2,
    }


def test_handling_latency_histogram_by_priority_bracket_excludes_open_and_acknowledged_cases():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=3)

    # Open-only case -> excluded.
    store.upsert_detection(
        _detection(case_type="stockout_risk", priority=90, run_id="run-open"),
        detected_at=opened_at,
    )

    # Acknowledged-only case -> excluded (no resolved_at).
    ack = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=65,
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

    # Fully handled -> counted; 4h tth -> under_6h, priority 30 -> low.
    handled_id = _handle(
        store,
        detection=_detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/conversation/wa-99/support.conversations/daily",
            severity="info",
            priority=30,
            run_id="run-handled",
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(minutes=10),
        resolved_at=opened_at + timedelta(minutes=10) + timedelta(hours=4),
    )

    result = summarize_case_handling_latency_histogram_by_priority_bracket(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_6h"] == 1
    assert result["by_handling_bucket_priority_bracket"]["under_6h"] == {"low": 1}
    assert result["fastest_handled"]["case_id"] == handled_id
    assert result["slowest_handled"]["case_id"] == handled_id


def test_handling_latency_histogram_by_priority_bracket_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=5)
    acknowledged_at = opened_at + timedelta(minutes=5)

    _handle(
        store,
        detection=_detection(
            business_id="artemea",
            priority=95,
            run_id="run-a",
        ),
        opened_at=opened_at,
        acknowledged_at=acknowledged_at,
        resolved_at=acknowledged_at + timedelta(hours=2),  # under_6h -> high
    )
    _handle(
        store,
        detection=_detection(
            business_id="other-shop",
            case_type="data_stale",
            dedupe_suffix="data_stale/business/monitored/observability.feeds/daily",
            severity="info",
            priority=20,
            run_id="run-other",
        ),
        opened_at=opened_at,
        acknowledged_at=acknowledged_at,
        resolved_at=acknowledged_at + timedelta(days=9),  # over_7d -> low
    )

    result = summarize_case_handling_latency_histogram_by_priority_bracket(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_6h"] == 1
    assert result["by_handling_bucket"]["over_7d"] == 0
    assert result["by_handling_bucket_priority_bracket"]["under_6h"] == {"high": 1}
    assert "low" not in result["by_handling_bucket_priority_bracket"]["over_7d"]


def test_handling_latency_histogram_by_priority_bracket_groups_multiple_cases_per_bucket():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)
    acknowledged_at = opened_at + timedelta(minutes=5)

    schedule = [
        (
            "a1",
            "stockout_risk",
            "stockout_risk/product/sku-a/commerce.inventory/daily",
            95,  # high
            timedelta(hours=2),  # under_6h
        ),
        (
            "a2",
            "stockout_risk",
            "stockout_risk/product/sku-b/commerce.inventory/daily",
            85,  # high
            timedelta(hours=4),  # under_6h
        ),
        (
            "a3",
            "sales_drop",
            "sales_drop/channel/meta_ads/commerce.revenue/daily",
            60,  # medium
            timedelta(hours=5),  # under_6h
        ),
        (
            "a4",
            "data_stale",
            "data_stale/business/monitored/observability.feeds/daily",
            15,  # low
            timedelta(days=8),  # over_7d
        ),
    ]
    for run_id, case_type, dedupe_suffix, priority, tth in schedule:
        _handle(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity="warning",
                priority=priority,
                run_id=f"run-{run_id}",
            ),
            opened_at=opened_at,
            acknowledged_at=acknowledged_at,
            resolved_at=acknowledged_at + tth,
        )

    result = summarize_case_handling_latency_histogram_by_priority_bracket(
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
    assert result["by_handling_bucket_priority_bracket"]["under_6h"] == {
        "high": 2,
        "medium": 1,
    }
    assert result["by_handling_bucket_priority_bracket"]["over_7d"] == {"low": 1}


def test_handling_latency_histogram_by_priority_bracket_clamps_non_positive_latency_to_zero():
    # Defensive: resolved_at == acknowledged_at -> 0s tth, still bucketed.
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(hours=2)
    acknowledged_at = opened_at + timedelta(minutes=1)

    _handle(
        store,
        detection=_detection(
            case_type="stockout_risk",
            priority=88,
            run_id="run-zero",
        ),
        opened_at=opened_at,
        acknowledged_at=acknowledged_at,
        resolved_at=acknowledged_at,
    )

    result = summarize_case_handling_latency_histogram_by_priority_bracket(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_1h"] == 1
    assert result["by_handling_bucket_priority_bracket"]["under_1h"] == {"high": 1}
    assert result["fastest_handled"]["time_to_handle_seconds"] == 0
    assert result["slowest_handled"]["time_to_handle_seconds"] == 0

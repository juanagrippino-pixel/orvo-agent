"""Tests for the priority-bracket-split case workflow throughput projection.

Mirrors :func:`summarize_case_workflow_throughput_by_source_connector` but
groups every count and latency aggregate by deterministic priority bracket
(low / medium / high) derived from ``case.priority_score``. Operator
surfaces use this to spot when high-priority cases drag acknowledgment or
resolution time even though severity, case_type, entity_kind and
source-connector aggregates look healthy.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    summarize_case_workflow_throughput_by_priority_bracket,
)


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/product/sku-1/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-throughput-pb-1",
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "product", "id": "sku-1", "label": "SKU 1"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def test_summarize_case_workflow_throughput_by_priority_bracket_returns_empty_summary_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_workflow_throughput_by_priority_bracket(
        store, business_id="artemea"
    )

    assert result == {
        "business_id": "artemea",
        "total": 0,
        "totals_by_priority_bracket": {},
        "acknowledged_by_priority_bracket": {},
        "resolved_by_priority_bracket": {},
        "time_to_acknowledge_seconds_by_priority_bracket": {},
        "time_to_resolve_seconds_by_priority_bracket": {},
    }


def test_summarize_case_workflow_throughput_by_priority_bracket_splits_latencies_per_bracket():
    store = InMemoryOperationalCaseStore()
    # high A: opened 08:00, acknowledged 11:00 (+3h), resolved 12:00 (+4h).
    a = store.upsert_detection(
        _detection(
            dedupe_suffix="stockout_risk/product/sku-a/commerce.inventory/daily",
            priority=95,  # high
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
    # high B: opened 08:00, acknowledged 09:00 (+1h) only.
    b = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/meta_ads/commerce.revenue/daily",
            severity="warning",
            priority=85,  # high
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
    # medium C: opened 08:00, acknowledged 13:00 (+5h), resolved 18:00 (+10h).
    c = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,  # medium
            run_id="run-c",
        ),
        detected_at=_utc(8),
    )
    store.transition_case(
        c.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(13),
    )
    store.transition_case(
        c.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved in test fixture",
        transitioned_at=_utc(18),
    )
    # low D: opened 08:00 and still open — counts toward totals only.
    store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/product/sku-d/support.conversations/daily",
            severity="info",
            priority=30,  # low
            run_id="run-d",
        ),
        detected_at=_utc(8),
    )

    result = summarize_case_workflow_throughput_by_priority_bracket(
        store, business_id="artemea"
    )

    assert result["business_id"] == "artemea"
    assert result["total"] == 4
    assert result["totals_by_priority_bracket"] == {
        "high": 2,
        "medium": 1,
        "low": 1,
    }
    assert result["acknowledged_by_priority_bracket"] == {
        "high": 2,
        "medium": 1,
    }
    assert result["resolved_by_priority_bracket"] == {
        "high": 1,
        "medium": 1,
    }
    # high ack: [3h, 1h] -> [10800, 3600]. medium ack: [5h] -> [18000].
    assert result["time_to_acknowledge_seconds_by_priority_bracket"] == {
        "high": {
            "min": 3600,
            "max": 10800,
            "avg": 7200,
            "median": 7200,
        },
        "medium": {
            "min": 18000,
            "max": 18000,
            "avg": 18000,
            "median": 18000,
        },
    }
    # high resolve: 4h, medium resolve: 10h.
    assert result["time_to_resolve_seconds_by_priority_bracket"] == {
        "high": {
            "min": 14400,
            "max": 14400,
            "avg": 14400,
            "median": 14400,
        },
        "medium": {
            "min": 36000,
            "max": 36000,
            "avg": 36000,
            "median": 36000,
        },
    }


def test_summarize_case_workflow_throughput_by_priority_bracket_buckets_score_boundaries():
    # Boundary-condition cases that pin the bracket cutoffs (same cutoffs as
    # _classify_priority_bracket):
    #   score < 50           -> "low"
    #   50 <= score < 80     -> "medium"
    #   80 <= score <= 100   -> "high"
    store = InMemoryOperationalCaseStore()
    schedule = [
        ("low-top", "stockout_risk/product/low-top/commerce.inventory/daily", 49),
        ("med-low", "stockout_risk/product/med-low/commerce.inventory/daily", 50),
        ("med-top", "stockout_risk/product/med-top/commerce.inventory/daily", 79),
        ("high-low", "stockout_risk/product/high-low/commerce.inventory/daily", 80),
        ("high-top", "stockout_risk/product/high-top/commerce.inventory/daily", 100),
        ("low-zero", "stockout_risk/product/low-zero/commerce.inventory/daily", 0),
    ]
    for run_id, dedupe_suffix, priority in schedule:
        store.upsert_detection(
            _detection(
                dedupe_suffix=dedupe_suffix,
                severity="warning",
                priority=priority,
                run_id=f"run-{run_id}",
            ),
            detected_at=_utc(8),
        )

    result = summarize_case_workflow_throughput_by_priority_bracket(
        store, business_id="artemea"
    )

    assert result["total"] == 6
    assert result["totals_by_priority_bracket"] == {
        "low": 2,
        "medium": 2,
        "high": 2,
    }
    # No transitions taken: per-bracket ack/resolve maps stay empty.
    assert result["acknowledged_by_priority_bracket"] == {}
    assert result["resolved_by_priority_bracket"] == {}
    assert result["time_to_acknowledge_seconds_by_priority_bracket"] == {}
    assert result["time_to_resolve_seconds_by_priority_bracket"] == {}


def test_summarize_case_workflow_throughput_by_priority_bracket_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    a = store.upsert_detection(
        _detection(
            business_id="artemea",
            priority=90,  # high
            run_id="run-a",
        ),
        detected_at=_utc(8),
    )
    store.transition_case(
        a.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(10),
    )
    other = store.upsert_detection(
        _detection(
            business_id="other-shop",
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=30,  # low — must not leak into artemea aggregates
            run_id="run-other",
        ),
        detected_at=_utc(8),
    )
    store.transition_case(
        other.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(20),
    )

    result = summarize_case_workflow_throughput_by_priority_bracket(
        store, business_id="artemea"
    )

    assert result["total"] == 1
    assert result["totals_by_priority_bracket"] == {"high": 1}
    assert result["acknowledged_by_priority_bracket"] == {"high": 1}
    assert result["resolved_by_priority_bracket"] == {}
    assert result["time_to_acknowledge_seconds_by_priority_bracket"] == {
        "high": {
            "min": 7200,
            "max": 7200,
            "avg": 7200,
            "median": 7200,
        }
    }
    assert result["time_to_resolve_seconds_by_priority_bracket"] == {}

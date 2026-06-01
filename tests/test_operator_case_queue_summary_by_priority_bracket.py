"""Tests for the priority-bracket-split case-queue summary projection.

``summarize_case_queue`` already exposes lifecycle counts by status, severity,
and case type. This projection mirrors it but groups every count by the
deterministic priority bracket (``low`` / ``medium`` / ``high``) derived from
``case.priority_score`` via ``_classify_priority_bracket``. Operator surfaces
use it to spot when high-priority work concentrates in the actionable backlog
even though the severity / case_type distributions look healthy.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseEvidenceSnapshot,
)
from app.brain.operator_api import summarize_case_queue_by_priority_bracket


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-summary-pb-1",
    freshness_state: str = "fresh",
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    snapshot = OperationalCaseEvidenceSnapshot(
        snapshot_key=f"{run_id}/{evidence_ref}/{case_type}/business/monitored",
        captured_at=_utc(8),
        run_id=run_id,
        artifact_ref=f"ledger://runs/{run_id}/daily-report",
        evidence_ref=evidence_ref,
        source="tiendanube",
        source_label="Tiendanube",
        case_type=case_type,  # type: ignore[arg-type]
        entity_scope={"kind": "business", "id": "monitored"},
        summary="Snapshot",
        freshness_state=freshness_state,  # type: ignore[arg-type]
    )
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
        evidence_snapshots=[snapshot],
    )


def _seed_mixed_queue() -> InMemoryOperationalCaseStore:
    store = InMemoryOperationalCaseStore()
    # Open critical high-priority stockout case.
    open_stockout = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/monitored/commerce.inventory/daily",
            severity="critical",
            priority=95,
            run_id="run-1",
        ),
        detected_at=_utc(8),
    )
    # Open warning medium-priority sales drop with degraded evidence.
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-2",
            freshness_state="degraded",
        ),
        detected_at=_utc(9),
    )
    # Open warning low-priority sales drop (different entity).
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/meta_ads/commerce.revenue/daily",
            severity="warning",
            priority=30,
            run_id="run-3",
        ),
        detected_at=_utc(10),
    )
    # Acknowledge the stockout case so it stays actionable but flips status.
    store.transition_case(
        open_stockout.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(11),
    )
    # Resolved medium-priority data_stale: counted in total but not actionable.
    resolved_stale = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="data_stale/connector/tiendanube/runtime.freshness/daily",
            severity="warning",
            priority=60,
            run_id="run-4",
        ),
        detected_at=_utc(9),
    )
    store.transition_case(
        resolved_stale.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(10),
    )
    store.transition_case(
        resolved_stale.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved in test fixture",
        transitioned_at=_utc(12),
    )
    # Cross-business case must be excluded by scoping.
    store.upsert_detection(
        _detection(
            business_id="other-shop",
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/monitored/commerce.inventory/daily",
            severity="critical",
            priority=10,
            run_id="run-5",
        ),
        detected_at=_utc(8),
    )
    return store


def test_summarize_case_queue_by_priority_bracket_groups_lifecycle_counts():
    store = _seed_mixed_queue()

    result = summarize_case_queue_by_priority_bracket(store, business_id="artemea")

    assert result["business_id"] == "artemea"
    assert result["total"] == 4
    # high=stockout(95), medium=sales_drop(70) + data_stale(60), low=sales_drop(30)
    assert result["totals_by_priority_bracket"] == {"high": 1, "medium": 2, "low": 1}
    # Actionable = open + acknowledged: stockout(high), sales_drop(medium), sales_drop(low)
    assert result["actionable_total"] == 3
    assert result["actionable_by_priority_bracket"] == {"high": 1, "medium": 1, "low": 1}
    # Only the medium-priority sales_drop has degraded evidence.
    assert result["actionable_degraded_by_priority_bracket"] == {"medium": 1}


def test_summarize_case_queue_by_priority_bracket_is_scoped_per_business():
    store = _seed_mixed_queue()

    result = summarize_case_queue_by_priority_bracket(store, business_id="other-shop")

    assert result["business_id"] == "other-shop"
    assert result["total"] == 1
    assert result["totals_by_priority_bracket"] == {"low": 1}
    assert result["actionable_total"] == 1
    assert result["actionable_by_priority_bracket"] == {"low": 1}
    assert result["actionable_degraded_by_priority_bracket"] == {}


def test_summarize_case_queue_by_priority_bracket_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_queue_by_priority_bracket(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "total": 0,
        "actionable_total": 0,
        "totals_by_priority_bracket": {},
        "actionable_by_priority_bracket": {},
        "actionable_degraded_by_priority_bracket": {},
    }


def test_summarize_case_queue_by_priority_bracket_classifies_score_boundaries():
    # Boundary-condition cases that pin the bracket cutoffs:
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

    result = summarize_case_queue_by_priority_bracket(store, business_id="artemea")

    assert result["total"] == 6
    assert result["totals_by_priority_bracket"] == {"low": 2, "medium": 2, "high": 2}
    assert result["actionable_total"] == 6
    assert result["actionable_by_priority_bracket"] == {"low": 2, "medium": 2, "high": 2}
    assert result["actionable_degraded_by_priority_bracket"] == {}


def test_summarize_case_queue_by_priority_bracket_excludes_resolved_from_actionable():
    store = InMemoryOperationalCaseStore()
    # High-priority open case stays actionable.
    store.upsert_detection(
        _detection(case_type="stockout_risk", priority=90, run_id="run-open"),
        detected_at=_utc(8),
    )
    # High-priority resolved case still counts toward total but not actionable.
    resolved = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="critical",
            priority=85,
            run_id="run-done",
        ),
        detected_at=_utc(8),
    )
    store.transition_case(
        resolved.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(9),
    )
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved in test fixture",
        transitioned_at=_utc(10),
    )

    result = summarize_case_queue_by_priority_bracket(store, business_id="artemea")

    assert result["total"] == 2
    assert result["totals_by_priority_bracket"] == {"high": 2}
    assert result["actionable_total"] == 1
    assert result["actionable_by_priority_bracket"] == {"high": 1}
    assert result["actionable_degraded_by_priority_bracket"] == {}

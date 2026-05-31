"""Tests for the case-type-split case-queue summary projection.

``summarize_case_queue`` already exposes lifecycle counts by status, severity,
and case type via the flat ``by_case_type`` mapping. This projection mirrors it
but groups the actionable / actionable-degraded slices by ``case.case_type``
too, matching :func:`summarize_case_queue_aging_by_case_type` and
:func:`summarize_case_workflow_throughput_by_case_type`. Operator surfaces use
it to spot which case family dominates the in-flight backlog even when severity
/ priority distributions look balanced — for example, a stockout_risk wave
hiding inside healthy aggregate counts.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseEvidenceSnapshot,
)
from app.brain.operator_api import summarize_case_queue_by_case_type


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-summary-ct-1",
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
    # Open critical stockout case.
    open_stockout = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/monitored/commerce.inventory/daily",
            severity="critical",
            run_id="run-1",
        ),
        detected_at=_utc(8),
    )
    # Open warning sales drop with degraded evidence.
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
    # Open warning sales drop on a different entity.
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/meta_ads/commerce.revenue/daily",
            severity="warning",
            priority=65,
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
    # Resolved data_stale: counted in total but not actionable.
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
        transitioned_at=_utc(12),
    )
    # Cross-business case must be excluded by scoping.
    store.upsert_detection(
        _detection(
            business_id="other-shop",
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/monitored/commerce.inventory/daily",
            severity="critical",
            run_id="run-5",
        ),
        detected_at=_utc(8),
    )
    return store


def test_summarize_case_queue_by_case_type_groups_lifecycle_counts():
    store = _seed_mixed_queue()

    result = summarize_case_queue_by_case_type(store, business_id="artemea")

    assert result["business_id"] == "artemea"
    assert result["total"] == 4
    # stockout_risk x1 (ack), sales_drop x2 (open), data_stale x1 (resolved)
    assert result["totals_by_case_type"] == {
        "stockout_risk": 1,
        "sales_drop": 2,
        "data_stale": 1,
    }
    # Actionable = open + acknowledged: stockout(ack), sales_drop x2 (open)
    assert result["actionable_total"] == 3
    assert result["actionable_by_case_type"] == {
        "stockout_risk": 1,
        "sales_drop": 2,
    }
    # Only the open warning sales_drop carries degraded evidence.
    assert result["actionable_degraded_by_case_type"] == {"sales_drop": 1}


def test_summarize_case_queue_by_case_type_is_scoped_per_business():
    store = _seed_mixed_queue()

    result = summarize_case_queue_by_case_type(store, business_id="other-shop")

    assert result["business_id"] == "other-shop"
    assert result["total"] == 1
    assert result["totals_by_case_type"] == {"stockout_risk": 1}
    assert result["actionable_total"] == 1
    assert result["actionable_by_case_type"] == {"stockout_risk": 1}
    assert result["actionable_degraded_by_case_type"] == {}


def test_summarize_case_queue_by_case_type_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_queue_by_case_type(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "total": 0,
        "actionable_total": 0,
        "totals_by_case_type": {},
        "actionable_by_case_type": {},
        "actionable_degraded_by_case_type": {},
    }


def test_summarize_case_queue_by_case_type_excludes_resolved_from_actionable():
    store = InMemoryOperationalCaseStore()
    # Open stockout stays actionable.
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open"),
        detected_at=_utc(8),
    )
    # Resolved sales_drop still counts toward total but not actionable.
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
        transitioned_at=_utc(10),
    )

    result = summarize_case_queue_by_case_type(store, business_id="artemea")

    assert result["total"] == 2
    assert result["totals_by_case_type"] == {"stockout_risk": 1, "sales_drop": 1}
    assert result["actionable_total"] == 1
    assert result["actionable_by_case_type"] == {"stockout_risk": 1}
    assert result["actionable_degraded_by_case_type"] == {}

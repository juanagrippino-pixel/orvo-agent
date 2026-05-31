"""Tests for the deterministic case-queue summary projection."""

from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseEvidenceSnapshot,
)
from app.brain.operator_api import summarize_case_queue


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-summary-1",
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
    # Open warning sales drop case with degraded evidence.
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
    # In-progress warning sales drop in a different entity scope (different dedupe).
    in_progress_sales = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/meta_ads/commerce.revenue/daily",
            severity="warning",
            priority=65,
            run_id="run-3",
        ),
        detected_at=_utc(10),
    )
    store.transition_case(
        in_progress_sales.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(11),
    )
    # Acknowledge one of the cases.
    store.transition_case(
        open_stockout.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(11),
    )
    # Seed a resolved data_stale case to verify resolved cases are still counted.
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


def test_summarize_case_queue_counts_by_status_severity_and_case_type():
    store = _seed_mixed_queue()

    result = summarize_case_queue(store, business_id="artemea")

    assert result["business_id"] == "artemea"
    assert result["total"] == 4
    assert result["by_status"] == {"open": 1, "in_progress": 1, "acknowledged": 1, "resolved": 1}
    assert result["by_severity"] == {"critical": 1, "warning": 3}
    assert result["by_case_type"] == {"stockout_risk": 1, "sales_drop": 2, "data_stale": 1}
    # Actionable = open + acknowledged + in_progress. The acknowledged stockout case is critical.
    assert result["actionable_total"] == 3
    assert result["actionable_by_severity"] == {"critical": 1, "warning": 2}
    # Degraded count only reflects actionable cases with non-fresh evidence snapshots.
    assert result["actionable_degraded"] == 1


def test_summarize_case_queue_is_scoped_per_business_and_excludes_other_tenants():
    store = _seed_mixed_queue()

    result = summarize_case_queue(store, business_id="other-shop")

    assert result["business_id"] == "other-shop"
    assert result["total"] == 1
    assert result["by_status"] == {"open": 1}
    assert result["by_severity"] == {"critical": 1}
    assert result["by_case_type"] == {"stockout_risk": 1}
    assert result["actionable_total"] == 1
    assert result["actionable_degraded"] == 0


def test_summarize_case_queue_returns_empty_summary_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_queue(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "total": 0,
        "by_status": {},
        "by_severity": {},
        "by_case_type": {},
        "actionable_total": 0,
        "actionable_by_severity": {},
        "actionable_degraded": 0,
    }

"""Operator dashboard aggregation endpoint tests."""
from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseEvidenceSnapshot,
)
from app.brain.operator_api import get_operator_dashboard
from app.brain.run_ledger import InMemoryRunLedger


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 29, hour, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-1",
    freshness_state: str = "degraded",
    source: str = "tiendanube",
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    snapshot = OperationalCaseEvidenceSnapshot(
        snapshot_key=f"{run_id}/{evidence_ref}/{case_type}/business/monitored",
        captured_at=_utc(8),
        run_id=run_id,
        artifact_ref=f"ledger://runs/{run_id}/daily-report",
        evidence_ref=evidence_ref,
        source=source,
        source_label=source.title(),
        case_type=case_type,  # type: ignore[arg-type]
        entity_scope={"kind": "business", "id": "monitored"},
        summary="Snapshot",
        freshness_state=freshness_state,  # type: ignore[arg-type]
    )
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso de prueba",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        evidence_snapshots=[snapshot],
    )


def test_dashboard_returns_aggregated_views() -> None:
    """Dashboard should return all key operator views in one call."""
    store = InMemoryOperationalCaseStore()
    ledger = InMemoryRunLedger()

    # Create some cases with different states
    store.upsert_detection(
        _detection(case_type="stockout_risk", priority=100, run_id="run-1", freshness_state="degraded"),
        detected_at=_utc(5),
    )
    store.upsert_detection(
        _detection(case_type="sales_drop", priority=70, run_id="run-2", freshness_state="stale", dedupe_suffix="sales_drop/channel/revenue"),
        detected_at=_utc(6),
    )
    case3 = store.upsert_detection(
        _detection(case_type="data_stale", priority=70, run_id="run-3", freshness_state="missing", dedupe_suffix="data_stale/connector/freshness"),
        detected_at=_utc(7),
    )
    store.transition_case(
        case3.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="op@example.com",
        transitioned_at=_utc(8),
    )

    # Add some runs
    ledger.create_run(business_id="artemea", trigger_type="scheduled", run_id="run-1", started_at=_utc(4))
    ledger.update_run("run-1", status="succeeded", finished_at=_utc(5))
    ledger.create_run(business_id="artemea", trigger_type="scheduled", run_id="run-2", started_at=_utc(5))
    ledger.update_run("run-2", status="failed", finished_at=_utc(6))

    result = get_operator_dashboard(store, ledger, business_id="artemea", now=_utc(12))

    # Verify structure
    assert result["business_id"] == "artemea"
    assert result["now"] == "2026-05-29T12:00:00Z"
    assert "case_queue_summary" in result
    assert "top_actionable_cases" in result
    assert "top_degraded_cases" in result
    assert "workflow_throughput" in result
    assert "resolution_latency_histogram" in result
    assert "acknowledgment_latency_histogram" in result
    assert "run_history" in result

    # Verify case_queue_summary has counts
    summary = result["case_queue_summary"]
    assert "total" in summary
    assert "by_status" in summary
    assert summary["total"] == 3
    assert summary["by_status"]["open"] == 2
    assert summary["by_status"]["acknowledged"] == 1

    # Verify top_actionable_cases
    top = result["top_actionable_cases"]
    assert "cases" in top
    assert top["count"] == 3
    assert top["cases"][0]["priority_score"] == 100  # Highest first

    # Verify degraded cases
    degraded = result["top_degraded_cases"]
    assert "cases" in degraded
    assert degraded["count"] == 3  # All three are degraded (non-fresh: degraded, stale, missing)

    # Verify workflow_throughput
    throughput = result["workflow_throughput"]
    assert "acknowledged_count" in throughput
    assert "resolved_count" in throughput

    # Verify histograms
    res_hist = result["resolution_latency_histogram"]
    assert "by_resolution_bucket" in res_hist
    assert "fastest_resolved" in res_hist
    ack_hist = result["acknowledgment_latency_histogram"]
    assert "by_acknowledgment_bucket" in ack_hist

    # Verify run_history
    runs = result["run_history"]
    assert "runs" in runs
    assert len(runs["runs"]) == 2


def test_dashboard_handles_empty_stores() -> None:
    """Dashboard should return empty collections when no data exists."""
    store = InMemoryOperationalCaseStore()
    ledger = InMemoryRunLedger()

    result = get_operator_dashboard(store, ledger, business_id="empty", now=_utc(10))

    assert result["business_id"] == "empty"
    assert result["case_queue_summary"]["total"] == 0
    assert result["top_actionable_cases"]["count"] == 0
    assert result["top_degraded_cases"]["count"] == 0
    assert len(result["run_history"]["runs"]) == 0


def test_dashboard_scopes_to_business_id() -> None:
    """Dashboard should only return data for the requested business."""
    store = InMemoryOperationalCaseStore()
    ledger = InMemoryRunLedger()

    # Add cases for two businesses
    store.upsert_detection(
        _detection(
            business_id="biz-a",
            case_type="stockout_risk",
            dedupe_suffix="stockout/biz-a",
            run_id="run-a",
        ),
        detected_at=_utc(6),
    )
    store.upsert_detection(
        _detection(
            business_id="biz-b",
            case_type="sales_drop",
            dedupe_suffix="sales/biz-b",
            run_id="run-b",
            source="meta_ads",
        ),
        detected_at=_utc(8),
    )

    result_a = get_operator_dashboard(store, ledger, business_id="biz-a", now=_utc(10))
    result_b = get_operator_dashboard(store, ledger, business_id="biz-b", now=_utc(10))

    assert result_a["case_queue_summary"]["total"] == 1
    assert result_a["top_actionable_cases"]["cases"][0]["case_type"] == "stockout_risk"

    assert result_b["case_queue_summary"]["total"] == 1
    assert result_b["top_actionable_cases"]["cases"][0]["case_type"] == "sales_drop"

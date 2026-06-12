"""Operator dashboard aggregation endpoint tests."""
from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseEvidenceSnapshot,
)
from app.brain.operator_api import get_operator_dashboard, get_os_snapshot
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
    metadata: dict | None = None,
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
        metadata=metadata or {},
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


def _module(snapshot: dict, module_key: str) -> dict:
    return next(module for module in snapshot["modules"] if module["module_key"] == module_key)


def test_os_snapshot_projects_module_health_queue_and_next_action() -> None:
    """OS snapshot derives module health, data health, and next action from case/run state."""
    store = InMemoryOperationalCaseStore()
    ledger = InMemoryRunLedger()

    stockout = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            priority=100,
            run_id="run-1",
            freshness_state="degraded",
            metadata={"suggested_action_keys": ["confirm_stock", "made_up_key", "review_campaigns"]},
        ),
        detected_at=_utc(5),
    )
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-2",
            freshness_state="fresh",
            dedupe_suffix="sales_drop/channel/revenue",
        ),
        detected_at=_utc(6),
    )
    store.upsert_detection(
        _detection(
            case_type="data_stale",
            severity="warning",
            priority=60,
            run_id="run-3",
            freshness_state="missing",
            dedupe_suffix="data_stale/connector/freshness",
        ),
        detected_at=_utc(7),
    )
    ledger.create_run(business_id="artemea", trigger_type="scheduled", run_id="run-1", started_at=_utc(4))
    ledger.update_run("run-1", status="succeeded", finished_at=_utc(5))

    result = get_os_snapshot(store, ledger, business_id="artemea", now=_utc(12))

    assert result["business_id"] == "artemea"
    assert result["now"] == "2026-05-29T12:00:00Z"

    # Stable module lanes in console order.
    assert [module["module_key"] for module in result["modules"]] == [
        "sales_orders",
        "stock_fulfillment",
        "customer_attention",
        "arca_fiscal",
        "treasury_reporting",
    ]

    sales = _module(result, "sales_orders")
    assert sales["lane"] == "automated"
    assert sales["status"] == "attention"
    assert sales["actionable_cases"] == 1
    assert sales["actionable_critical"] == 0
    assert sales["degraded_cases"] == 0
    assert "sales_drop" in sales["owner_facing_case_families"]
    assert "spend_without_orders" not in sales["owner_facing_case_families"]

    stock = _module(result, "stock_fulfillment")
    assert stock["lane"] == "automated"
    assert stock["status"] == "attention"
    assert stock["actionable_cases"] == 1
    assert stock["actionable_critical"] == 1
    assert stock["degraded_cases"] == 1

    attention = _module(result, "customer_attention")
    assert attention["lane"] == "readiness_gated"
    assert attention["status"] == "setup_required"
    assert attention["actionable_cases"] == 0

    for readiness_key in ("arca_fiscal", "treasury_reporting"):
        lane = _module(result, readiness_key)
        assert lane["lane"] == "readiness_lane"
        assert lane["status"] == "not_connected"
        assert lane["case_families"] == []

    # data_stale is cross-cutting data truth, not a module backlog.
    assert result["data_health"]["case_family"] == "data_stale"
    assert result["data_health"]["actionable_cases"] == 1
    assert result["data_health"]["status"] == "attention"

    assert result["case_queue_summary"]["total"] == 3
    assert result["case_queue_summary"]["by_status"]["open"] == 3

    next_action = result["next_action"]
    assert next_action["kind"] == "work_case"
    assert next_action["case"]["case_id"] == stockout.case_id
    assert next_action["case"]["priority_score"] == 100
    # Only registered action keys allowed for the case family survive projection.
    assert next_action["suggested_action_keys"] == ["confirm_stock"]
    assert next_action["lifecycle_action_key"] == "acknowledge_case"

    runtime = result["runtime_health"]
    assert runtime["latest_run"]["run_id"] == "run-1"
    assert runtime["latest_run_status"] == "succeeded"


def test_os_snapshot_next_action_follows_case_lifecycle() -> None:
    """Lifecycle next-action key advances with deterministic case transitions."""
    store = InMemoryOperationalCaseStore()
    ledger = InMemoryRunLedger()
    case = store.upsert_detection(_detection(case_type="stockout_risk", priority=100), detected_at=_utc(5))

    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="op@example.com",
        transitioned_at=_utc(6),
    )
    acknowledged = get_os_snapshot(store, ledger, business_id="artemea", now=_utc(7))
    assert acknowledged["next_action"]["lifecycle_action_key"] == "mark_in_progress"

    store.transition_case(
        case.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="op@example.com",
        transitioned_at=_utc(8),
    )
    in_progress = get_os_snapshot(store, ledger, business_id="artemea", now=_utc(9))
    assert in_progress["next_action"]["lifecycle_action_key"] == "resolve_case"


def test_os_snapshot_empty_business_is_calm_not_fabricated() -> None:
    """Without cases or runs the snapshot reports all-clear without inventing data."""
    store = InMemoryOperationalCaseStore()
    ledger = InMemoryRunLedger()

    result = get_os_snapshot(store, ledger, business_id="empty", now=_utc(10))

    assert _module(result, "sales_orders")["status"] == "ok"
    assert _module(result, "stock_fulfillment")["status"] == "ok"
    assert _module(result, "customer_attention")["status"] == "setup_required"
    assert _module(result, "arca_fiscal")["status"] == "not_connected"
    assert result["data_health"]["status"] == "ok"
    assert result["case_queue_summary"]["total"] == 0
    assert result["next_action"] == {
        "kind": "all_clear",
        "case": None,
        "suggested_action_keys": [],
        "lifecycle_action_key": None,
    }
    assert result["runtime_health"]["latest_run"] is None
    assert result["runtime_health"]["latest_run_status"] is None


def test_os_snapshot_scopes_to_business_id() -> None:
    """Snapshot never leaks another tenant's cases or runs."""
    store = InMemoryOperationalCaseStore()
    ledger = InMemoryRunLedger()
    store.upsert_detection(
        _detection(business_id="biz-a", case_type="stockout_risk", dedupe_suffix="stockout/biz-a"),
        detected_at=_utc(6),
    )
    ledger.create_run(business_id="biz-a", trigger_type="scheduled", run_id="run-a", started_at=_utc(4))

    result_b = get_os_snapshot(store, ledger, business_id="biz-b", now=_utc(10))

    assert result_b["case_queue_summary"]["total"] == 0
    assert result_b["next_action"]["kind"] == "all_clear"
    assert result_b["runtime_health"]["latest_run"] is None

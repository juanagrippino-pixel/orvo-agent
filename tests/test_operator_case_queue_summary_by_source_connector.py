"""Tests for the source-connector-split case-queue summary projection.

``summarize_case_queue`` already exposes lifecycle counts by status, severity,
and case type. This projection mirrors it but groups every count by the
source connector (tiendanube / google_sheets / csv / etc.) derived from the
alphabetically-first evidence snapshot source, matching
:func:`summarize_case_queue_aging_by_source_connector` and
:func:`summarize_case_workflow_throughput_by_source_connector`. Operator
surfaces use it to spot when a single ingestion path dominates the
actionable backlog even when the severity / case_type distributions look
balanced (for example, a Tiendanube ingestion incident concentrating cases
under that connector).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseEvidenceSnapshot,
)
from app.brain.operator_api import summarize_case_queue_by_source_connector


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-summary-source-1",
    freshness_state: str = "fresh",
    source: str = "tiendanube",
    source_label: str = "Tiendanube",
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    snapshot = OperationalCaseEvidenceSnapshot(
        snapshot_key=f"{run_id}/{evidence_ref}/{case_type}/business/monitored",
        captured_at=_utc(8),
        run_id=run_id,
        artifact_ref=f"ledger://runs/{run_id}/daily-report",
        evidence_ref=evidence_ref,
        source=source,
        source_label=source_label,
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
    # Open critical stockout case (tiendanube).
    open_stockout = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/monitored/commerce.inventory/daily",
            severity="critical",
            run_id="run-1",
            source="tiendanube",
        ),
        detected_at=_utc(8),
    )
    # Open warning sales drop on google_sheets with degraded evidence.
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-2",
            freshness_state="degraded",
            source="google_sheets",
            source_label="Google Sheets",
        ),
        detected_at=_utc(9),
    )
    # Open warning sales drop on google_sheets (different entity).
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/meta_ads/commerce.revenue/daily",
            severity="warning",
            priority=65,
            run_id="run-3",
            source="google_sheets",
            source_label="Google Sheets",
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
    # Resolved data_stale on csv: counted in total but not actionable.
    resolved_stale = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="data_stale/connector/tiendanube/runtime.freshness/daily",
            severity="warning",
            priority=60,
            run_id="run-4",
            source="csv",
            source_label="CSV",
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
            source="tiendanube",
        ),
        detected_at=_utc(8),
    )
    return store


def test_summarize_case_queue_by_source_connector_groups_lifecycle_counts():
    store = _seed_mixed_queue()

    result = summarize_case_queue_by_source_connector(store, business_id="artemea")

    assert result["business_id"] == "artemea"
    assert result["total"] == 4
    # tiendanube: stockout(ack); google_sheets: sales_drop x2 (open); csv: data_stale(resolved)
    assert result["totals_by_source_connector"] == {
        "tiendanube": 1,
        "google_sheets": 2,
        "csv": 1,
    }
    # Actionable = open + acknowledged: stockout(tiendanube) + sales_drop x2(google_sheets)
    assert result["actionable_total"] == 3
    assert result["actionable_by_source_connector"] == {
        "tiendanube": 1,
        "google_sheets": 2,
    }
    # Only the open google_sheets sales_drop carries degraded evidence.
    assert result["actionable_degraded_by_source_connector"] == {"google_sheets": 1}


def test_summarize_case_queue_by_source_connector_is_scoped_per_business():
    store = _seed_mixed_queue()

    result = summarize_case_queue_by_source_connector(store, business_id="other-shop")

    assert result["business_id"] == "other-shop"
    assert result["total"] == 1
    assert result["totals_by_source_connector"] == {"tiendanube": 1}
    assert result["actionable_total"] == 1
    assert result["actionable_by_source_connector"] == {"tiendanube": 1}
    assert result["actionable_degraded_by_source_connector"] == {}


def test_summarize_case_queue_by_source_connector_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_queue_by_source_connector(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "total": 0,
        "actionable_total": 0,
        "totals_by_source_connector": {},
        "actionable_by_source_connector": {},
        "actionable_degraded_by_source_connector": {},
    }


def test_summarize_case_queue_by_source_connector_excludes_resolved_from_actionable():
    store = InMemoryOperationalCaseStore()
    # Open tiendanube case stays actionable.
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open", source="tiendanube"),
        detected_at=_utc(8),
    )
    # Resolved google_sheets case still counts toward total but not actionable.
    resolved = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="critical",
            priority=85,
            run_id="run-done",
            source="google_sheets",
            source_label="Google Sheets",
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

    result = summarize_case_queue_by_source_connector(store, business_id="artemea")

    assert result["total"] == 2
    assert result["totals_by_source_connector"] == {"tiendanube": 1, "google_sheets": 1}
    assert result["actionable_total"] == 1
    assert result["actionable_by_source_connector"] == {"tiendanube": 1}
    assert result["actionable_degraded_by_source_connector"] == {}


def test_summarize_case_queue_by_source_connector_buckets_cases_without_evidence_as_unknown():
    # Detections built without explicit snapshots fall back to source extracted
    # from the evidence_ref host segment. When that host is non-routable (or the
    # evidence_ref isn't an ``evidence://`` URI), ``_source_from_evidence_ref``
    # yields ``"unknown"`` and we must surface that bucket explicitly rather
    # than silently drop the case from the per-source counts.
    store = InMemoryOperationalCaseStore()
    detection = OperationalCaseDetection(
        business_id="artemea",
        case_type="stockout_risk",  # type: ignore[arg-type]
        dedupe_key="artemea/stockout_risk/product/sku-x/commerce.inventory/daily",
        title="Caso",
        severity="warning",  # type: ignore[arg-type]
        priority_score=70,
        entity_scope={"kind": "product", "id": "sku-x", "label": "SKU X"},
        evidence_refs=["ledger://anonymous/no-source"],
        run_id="run-no-source",
        artifact_refs=["ledger://runs/run-no-source/daily-report"],
    )
    store.upsert_detection(detection, detected_at=_utc(8))

    result = summarize_case_queue_by_source_connector(store, business_id="artemea")

    assert result["total"] == 1
    assert result["totals_by_source_connector"] == {"unknown": 1}
    assert result["actionable_total"] == 1
    assert result["actionable_by_source_connector"] == {"unknown": 1}
    assert result["actionable_degraded_by_source_connector"] == {}

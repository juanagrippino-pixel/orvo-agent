"""Tests for the entity-kind-split case-queue summary projection.

``summarize_case_queue`` already exposes lifecycle counts by status, severity,
and case type. This projection mirrors it but groups every count by
``entity_scope.kind`` (product / channel / business / connector / etc.),
matching the attribution used by
:func:`summarize_case_queue_aging_by_entity_kind`,
:func:`summarize_case_queue_stagnation_by_entity_kind`, and
:func:`summarize_case_workflow_throughput_by_entity_kind`. Operator surfaces
use it to spot when a single entity scope dominates the actionable backlog
even when severity / case_type / source distributions look balanced — for
example, a wave of product-scoped stockouts hiding behind aggregate counts
that include channel- and business-scoped cases.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseEvidenceSnapshot,
)
from app.brain.operator_api import summarize_case_queue_by_entity_kind


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/product/sku-1/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-summary-entity-1",
    freshness_state: str = "fresh",
    entity_scope: dict[str, str] | None = None,
) -> OperationalCaseDetection:
    scope = (
        entity_scope
        if entity_scope is not None
        else {"kind": "product", "id": "sku-1", "label": "SKU 1"}
    )
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    snapshot = OperationalCaseEvidenceSnapshot(
        snapshot_key=f"{run_id}/{evidence_ref}/{case_type}/{scope['kind']}/{scope['id']}",
        captured_at=_utc(8),
        run_id=run_id,
        artifact_ref=f"ledger://runs/{run_id}/daily-report",
        evidence_ref=evidence_ref,
        source="tiendanube",
        source_label="Tiendanube",
        case_type=case_type,  # type: ignore[arg-type]
        entity_scope={"kind": scope["kind"], "id": scope["id"]},
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
        entity_scope=scope,
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        evidence_snapshots=[snapshot],
    )


def _seed_mixed_queue() -> InMemoryOperationalCaseStore:
    store = InMemoryOperationalCaseStore()
    # Open critical product-scoped stockout case.
    open_stockout = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/product/sku-1/commerce.inventory/daily",
            severity="critical",
            run_id="run-1",
            entity_scope={"kind": "product", "id": "sku-1", "label": "SKU 1"},
        ),
        detected_at=_utc(8),
    )
    # Open warning channel-scoped sales drop with degraded evidence.
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-2",
            freshness_state="degraded",
            entity_scope={"kind": "channel", "id": "all", "label": "All"},
        ),
        detected_at=_utc(9),
    )
    # Open warning channel-scoped sales drop on a different channel.
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/meta_ads/commerce.revenue/daily",
            severity="warning",
            priority=65,
            run_id="run-3",
            entity_scope={"kind": "channel", "id": "meta_ads", "label": "Meta Ads"},
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
    # Resolved connector-scoped data_stale: counted in total but not actionable.
    resolved_stale = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="data_stale/connector/tiendanube/runtime.freshness/daily",
            severity="warning",
            priority=60,
            run_id="run-4",
            entity_scope={"kind": "connector", "id": "tiendanube", "label": "Tiendanube"},
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
            dedupe_suffix="stockout_risk/product/sku-9/commerce.inventory/daily",
            severity="critical",
            run_id="run-5",
            entity_scope={"kind": "product", "id": "sku-9", "label": "SKU 9"},
        ),
        detected_at=_utc(8),
    )
    return store


def test_summarize_case_queue_by_entity_kind_groups_lifecycle_counts():
    store = _seed_mixed_queue()

    result = summarize_case_queue_by_entity_kind(store, business_id="artemea")

    assert result["business_id"] == "artemea"
    assert result["total"] == 4
    # product: stockout(ack); channel: sales_drop x2 (open); connector: data_stale(resolved)
    assert result["totals_by_entity_kind"] == {
        "product": 1,
        "channel": 2,
        "connector": 1,
    }
    # Actionable = open + acknowledged: stockout(product) + sales_drop x2(channel)
    assert result["actionable_total"] == 3
    assert result["actionable_by_entity_kind"] == {
        "product": 1,
        "channel": 2,
    }
    # Only the open channel sales_drop on "all" carries degraded evidence.
    assert result["actionable_degraded_by_entity_kind"] == {"channel": 1}


def test_summarize_case_queue_by_entity_kind_is_scoped_per_business():
    store = _seed_mixed_queue()

    result = summarize_case_queue_by_entity_kind(store, business_id="other-shop")

    assert result["business_id"] == "other-shop"
    assert result["total"] == 1
    assert result["totals_by_entity_kind"] == {"product": 1}
    assert result["actionable_total"] == 1
    assert result["actionable_by_entity_kind"] == {"product": 1}
    assert result["actionable_degraded_by_entity_kind"] == {}


def test_summarize_case_queue_by_entity_kind_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_queue_by_entity_kind(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "total": 0,
        "actionable_total": 0,
        "totals_by_entity_kind": {},
        "actionable_by_entity_kind": {},
        "actionable_degraded_by_entity_kind": {},
    }


def test_summarize_case_queue_by_entity_kind_excludes_resolved_from_actionable():
    store = InMemoryOperationalCaseStore()
    # Open product-scoped case stays actionable.
    store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            run_id="run-open",
            entity_scope={"kind": "product", "id": "sku-a", "label": "SKU A"},
        ),
        detected_at=_utc(8),
    )
    # Resolved channel-scoped case still counts toward total but not actionable.
    resolved = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="critical",
            priority=85,
            run_id="run-done",
            entity_scope={"kind": "channel", "id": "all", "label": "All"},
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

    result = summarize_case_queue_by_entity_kind(store, business_id="artemea")

    assert result["total"] == 2
    assert result["totals_by_entity_kind"] == {"product": 1, "channel": 1}
    assert result["actionable_total"] == 1
    assert result["actionable_by_entity_kind"] == {"product": 1}
    assert result["actionable_degraded_by_entity_kind"] == {}


def test_summarize_case_queue_by_entity_kind_buckets_missing_kind_as_unknown():
    """A case whose ``entity_scope`` lacks a ``kind`` must be bucketed under
    ``"unknown"`` rather than silently dropped, matching how
    :func:`summarize_case_queue_aging_by_entity_kind` handles the same gap.
    """

    store = InMemoryOperationalCaseStore()
    detection = OperationalCaseDetection(
        business_id="artemea",
        case_type="stockout_risk",  # type: ignore[arg-type]
        dedupe_key="artemea/stockout_risk/unknown/none/commerce.inventory/daily",
        title="Caso",
        severity="warning",  # type: ignore[arg-type]
        priority_score=70,
        entity_scope={"id": "none", "label": "Sin scope"},
        evidence_refs=["evidence://artemea/run-x/stockout_risk"],
        run_id="run-no-kind",
        artifact_refs=["ledger://runs/run-no-kind/daily-report"],
    )
    store.upsert_detection(detection, detected_at=_utc(8))

    result = summarize_case_queue_by_entity_kind(store, business_id="artemea")

    assert result["total"] == 1
    assert result["totals_by_entity_kind"] == {"unknown": 1}
    assert result["actionable_total"] == 1
    assert result["actionable_by_entity_kind"] == {"unknown": 1}
    assert result["actionable_degraded_by_entity_kind"] == {}

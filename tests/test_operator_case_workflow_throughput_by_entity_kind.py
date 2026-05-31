"""Tests for the entity-kind-split case workflow throughput projection."""

from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import summarize_case_workflow_throughput_by_entity_kind


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/product/sku-1/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-throughput-entity-1",
    entity_scope: dict[str, str] | None = None,
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope=(
            entity_scope
            if entity_scope is not None
            else {"kind": "product", "id": "sku-1", "label": "SKU 1"}
        ),
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def test_summarize_case_workflow_throughput_by_entity_kind_returns_empty_summary_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_workflow_throughput_by_entity_kind(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "total": 0,
        "totals_by_entity_kind": {},
        "acknowledged_by_entity_kind": {},
        "resolved_by_entity_kind": {},
        "time_to_acknowledge_seconds_by_entity_kind": {},
        "time_to_resolve_seconds_by_entity_kind": {},
    }


def test_summarize_case_workflow_throughput_by_entity_kind_splits_latencies_per_entity_kind():
    store = InMemoryOperationalCaseStore()
    # product A: opened 08:00, acknowledged 11:00, resolved 12:00.
    a = store.upsert_detection(
        _detection(
            dedupe_suffix="stockout_risk/product/sku-a/commerce.inventory/daily",
            run_id="run-a",
            entity_scope={"kind": "product", "id": "sku-a", "label": "SKU A"},
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
    # channel B: opened 08:00, acknowledged 13:00, resolved 18:00.
    b = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-b",
            entity_scope={"kind": "channel", "id": "all", "label": "Todos"},
        ),
        detected_at=_utc(8),
    )
    store.transition_case(
        b.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(13),
    )
    store.transition_case(
        b.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved in test fixture",
        transitioned_at=_utc(18),
    )
    # channel C: opened 08:00, acknowledged 09:00 only.
    c = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/meta_ads/commerce.revenue/daily",
            severity="warning",
            priority=65,
            run_id="run-c",
            entity_scope={"kind": "channel", "id": "meta_ads", "label": "Meta Ads"},
        ),
        detected_at=_utc(8),
    )
    store.transition_case(
        c.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(9),
    )
    # product D: opened 08:00 and still open — counts toward totals only.
    store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/product/sku-d/support.conversations/daily",
            severity="warning",
            priority=60,
            run_id="run-d",
            entity_scope={"kind": "product", "id": "sku-d", "label": "SKU D"},
        ),
        detected_at=_utc(8),
    )

    result = summarize_case_workflow_throughput_by_entity_kind(store, business_id="artemea")

    assert result["business_id"] == "artemea"
    assert result["total"] == 4
    assert result["totals_by_entity_kind"] == {
        "product": 2,
        "channel": 2,
    }
    assert result["acknowledged_by_entity_kind"] == {
        "product": 1,
        "channel": 2,
    }
    assert result["resolved_by_entity_kind"] == {
        "product": 1,
        "channel": 1,
    }
    # product ack: [3h] -> [10800]. channel ack: [1h, 5h] -> [3600, 18000].
    assert result["time_to_acknowledge_seconds_by_entity_kind"] == {
        "product": {
            "min": 10800,
            "max": 10800,
            "avg": 10800,
            "median": 10800,
        },
        "channel": {
            "min": 3600,
            "max": 18000,
            "avg": 10800,
            "median": 10800,
        },
    }
    # product resolve: [4h] -> [14400]. channel resolve: [10h] -> [36000].
    assert result["time_to_resolve_seconds_by_entity_kind"] == {
        "product": {
            "min": 14400,
            "max": 14400,
            "avg": 14400,
            "median": 14400,
        },
        "channel": {
            "min": 36000,
            "max": 36000,
            "avg": 36000,
            "median": 36000,
        },
    }


def test_summarize_case_workflow_throughput_by_entity_kind_buckets_missing_kind_as_unknown():
    store = InMemoryOperationalCaseStore()
    # Case with empty entity_scope -> should bucket under "unknown".
    a = store.upsert_detection(
        _detection(
            dedupe_suffix="stockout_risk/unknown/sku-x/commerce.inventory/daily",
            run_id="run-x",
            entity_scope={},
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

    result = summarize_case_workflow_throughput_by_entity_kind(store, business_id="artemea")

    assert result["totals_by_entity_kind"] == {"unknown": 1}
    assert result["acknowledged_by_entity_kind"] == {"unknown": 1}
    assert result["time_to_acknowledge_seconds_by_entity_kind"] == {
        "unknown": {
            "min": 7200,
            "max": 7200,
            "avg": 7200,
            "median": 7200,
        }
    }


def test_summarize_case_workflow_throughput_by_entity_kind_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    a = store.upsert_detection(
        _detection(
            business_id="artemea",
            run_id="run-a",
            entity_scope={"kind": "product", "id": "sku-a", "label": "SKU A"},
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
            run_id="run-other",
            entity_scope={"kind": "channel", "id": "all", "label": "Todos"},
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

    result = summarize_case_workflow_throughput_by_entity_kind(store, business_id="artemea")

    assert result["total"] == 1
    assert result["totals_by_entity_kind"] == {"product": 1}
    assert result["acknowledged_by_entity_kind"] == {"product": 1}
    assert result["resolved_by_entity_kind"] == {}
    assert result["time_to_acknowledge_seconds_by_entity_kind"] == {
        "product": {
            "min": 7200,
            "max": 7200,
            "avg": 7200,
            "median": 7200,
        }
    }
    assert result["time_to_resolve_seconds_by_entity_kind"] == {}

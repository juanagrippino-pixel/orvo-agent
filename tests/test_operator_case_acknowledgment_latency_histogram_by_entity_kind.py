"""Tests for the entity-kind-split acknowledgment-latency histogram projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    summarize_case_acknowledgment_latency_histogram_by_entity_kind,
)


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/product/sku-1/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-ack-ek-1",
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


def _empty_buckets() -> dict[str, int]:
    return {"under_1h": 0, "under_6h": 0, "under_24h": 0, "under_7d": 0, "over_7d": 0}


def _acknowledge(
    store: InMemoryOperationalCaseStore,
    *,
    detection: OperationalCaseDetection,
    opened_at: datetime,
    acknowledged_at: datetime,
) -> str:
    case = store.upsert_detection(detection, detected_at=opened_at)
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=acknowledged_at,
    )
    return case.case_id


def test_acknowledgment_latency_histogram_by_entity_kind_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_acknowledgment_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result == {
        "business_id": "artemea",
        "acknowledged_total": 0,
        "by_acknowledgment_bucket": _empty_buckets(),
        "by_acknowledgment_bucket_entity_kind": {bucket: {} for bucket in _empty_buckets()},
        "fastest_acknowledged": None,
        "slowest_acknowledged": None,
    }


def test_acknowledgment_latency_histogram_by_entity_kind_buckets_by_entity_kind():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    schedule = [
        (
            "a",
            "stockout_risk",
            "stockout_risk/product/sku-a/commerce.inventory/daily",
            {"kind": "product", "id": "sku-a", "label": "SKU A"},
            timedelta(minutes=30),
        ),
        (
            "b",
            "sales_drop",
            "sales_drop/channel/all/commerce.revenue/daily",
            {"kind": "channel", "id": "all", "label": "Todos"},
            timedelta(hours=3),
        ),
        (
            "c",
            "sales_drop",
            "sales_drop/channel/meta_ads/commerce.revenue/daily",
            {"kind": "channel", "id": "meta_ads", "label": "Meta Ads"},
            timedelta(hours=10),
        ),
        (
            "d",
            "unanswered_conversations",
            "unanswered_conversations/conversation/wa-99/support.conversations/daily",
            {"kind": "conversation", "id": "wa-99", "label": "WA 99"},
            timedelta(days=2),
        ),
        (
            "e",
            "data_stale",
            "data_stale/business/monitored/observability.feeds/daily",
            {"kind": "business", "id": "monitored", "label": "Monitoreado"},
            timedelta(days=10),
        ),
    ]
    for run_id, case_type, dedupe_suffix, entity_scope, tta in schedule:
        _acknowledge(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity="warning",
                priority=70,
                run_id=f"run-{run_id}",
                entity_scope=entity_scope,
            ),
            opened_at=opened_at,
            acknowledged_at=opened_at + tta,
        )

    result = summarize_case_acknowledgment_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result["acknowledged_total"] == 5
    assert result["by_acknowledgment_bucket"] == {
        "under_1h": 1,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 1,
        "over_7d": 1,
    }
    assert result["by_acknowledgment_bucket_entity_kind"] == {
        "under_1h": {"product": 1},
        "under_6h": {"channel": 1},
        "under_24h": {"channel": 1},
        "under_7d": {"conversation": 1},
        "over_7d": {"business": 1},
    }
    fastest = result["fastest_acknowledged"]
    slowest = result["slowest_acknowledged"]
    assert fastest is not None and slowest is not None
    assert fastest["time_to_acknowledge_seconds"] == int(timedelta(minutes=30).total_seconds())
    assert fastest["case_type"] == "stockout_risk"
    assert slowest["time_to_acknowledge_seconds"] == int(timedelta(days=10).total_seconds())
    assert slowest["case_type"] == "data_stale"


def test_acknowledgment_latency_histogram_by_entity_kind_excludes_open_only_cases():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=3)

    # Open-only case — must be excluded.
    store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            run_id="run-open",
            entity_scope={"kind": "product", "id": "sku-open", "label": "SKU Open"},
        ),
        detected_at=opened_at,
    )

    # Acknowledged case — 4h time-to-acknowledge -> under_6h.
    ack_id = _acknowledge(
        store,
        detection=_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-ack",
            entity_scope={"kind": "channel", "id": "all", "label": "Todos"},
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=4),
    )

    result = summarize_case_acknowledgment_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result["acknowledged_total"] == 1
    assert result["by_acknowledgment_bucket"]["under_6h"] == 1
    assert result["by_acknowledgment_bucket"]["under_1h"] == 0
    assert result["by_acknowledgment_bucket_entity_kind"]["under_6h"] == {
        "channel": 1,
    }
    assert result["fastest_acknowledged"]["case_id"] == ack_id
    assert result["slowest_acknowledged"]["case_id"] == ack_id


def test_acknowledgment_latency_histogram_by_entity_kind_includes_resolved_cases():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=3)

    case = store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/conversation/wa-1/support.conversations/daily",
            severity="warning",
            priority=70,
            run_id="run-resolved",
            entity_scope={"kind": "conversation", "id": "wa-1", "label": "WA 1"},
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=opened_at + timedelta(hours=2),
    )
    store.transition_case(
        case.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved in test fixture",
        transitioned_at=opened_at + timedelta(hours=6),
    )

    result = summarize_case_acknowledgment_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result["acknowledged_total"] == 1
    assert result["by_acknowledgment_bucket"]["under_6h"] == 1
    assert result["by_acknowledgment_bucket_entity_kind"]["under_6h"] == {
        "conversation": 1,
    }


def test_acknowledgment_latency_histogram_by_entity_kind_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=5)

    _acknowledge(
        store,
        detection=_detection(
            business_id="artemea",
            run_id="run-a",
            entity_scope={"kind": "product", "id": "sku-a", "label": "SKU A"},
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=2),
    )
    _acknowledge(
        store,
        detection=_detection(
            business_id="other-shop",
            case_type="data_stale",
            dedupe_suffix="data_stale/business/monitored/observability.feeds/daily",
            severity="info",
            run_id="run-other",
            entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(days=8),
    )

    result = summarize_case_acknowledgment_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result["acknowledged_total"] == 1
    assert result["by_acknowledgment_bucket"]["under_6h"] == 1
    assert result["by_acknowledgment_bucket"]["over_7d"] == 0
    assert result["by_acknowledgment_bucket_entity_kind"]["under_6h"] == {
        "product": 1,
    }
    assert "business" not in result["by_acknowledgment_bucket_entity_kind"]["over_7d"]


def test_acknowledgment_latency_histogram_by_entity_kind_groups_multiple_cases_per_bucket():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    schedule = [
        (
            "a1",
            "stockout_risk",
            "stockout_risk/product/sku-a/commerce.inventory/daily",
            {"kind": "product", "id": "sku-a", "label": "SKU A"},
            timedelta(hours=2),
        ),
        (
            "a2",
            "stockout_risk",
            "stockout_risk/product/sku-b/commerce.inventory/daily",
            {"kind": "product", "id": "sku-b", "label": "SKU B"},
            timedelta(hours=4),
        ),
        (
            "a3",
            "sales_drop",
            "sales_drop/channel/meta_ads/commerce.revenue/daily",
            {"kind": "channel", "id": "meta_ads", "label": "Meta Ads"},
            timedelta(hours=5),
        ),
        (
            "a4",
            "data_stale",
            "data_stale/business/monitored/observability.feeds/daily",
            {"kind": "business", "id": "monitored", "label": "Monitoreado"},
            timedelta(days=8),
        ),
    ]
    for run_id, case_type, dedupe_suffix, entity_scope, tta in schedule:
        _acknowledge(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity="warning",
                priority=70,
                run_id=f"run-{run_id}",
                entity_scope=entity_scope,
            ),
            opened_at=opened_at,
            acknowledged_at=opened_at + tta,
        )

    result = summarize_case_acknowledgment_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result["acknowledged_total"] == 4
    assert result["by_acknowledgment_bucket"] == {
        "under_1h": 0,
        "under_6h": 3,
        "under_24h": 0,
        "under_7d": 0,
        "over_7d": 1,
    }
    assert result["by_acknowledgment_bucket_entity_kind"]["under_6h"] == {
        "product": 2,
        "channel": 1,
    }
    assert result["by_acknowledgment_bucket_entity_kind"]["over_7d"] == {"business": 1}


def test_acknowledgment_latency_histogram_by_entity_kind_buckets_missing_kind_as_unknown():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=2)

    _acknowledge(
        store,
        detection=_detection(
            case_type="data_stale",
            dedupe_suffix="data_stale/business/monitored/observability.feeds/daily",
            severity="info",
            run_id="run-no-kind",
            entity_scope={"id": "unknown-entity", "label": "Sin tipo"},
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=3),
    )

    result = summarize_case_acknowledgment_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result["acknowledged_total"] == 1
    assert result["by_acknowledgment_bucket"]["under_6h"] == 1
    assert result["by_acknowledgment_bucket_entity_kind"]["under_6h"] == {"unknown": 1}

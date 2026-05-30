"""Tests for the entity-kind-split handling-latency histogram projection.

Handling latency = ``resolved_at - acknowledged_at`` (operator working
time). This projection mirrors
:func:`summarize_case_handling_latency_histogram` but groups each bucket
by ``entity_scope.kind`` (product/channel/business/conversation/etc.) so
operator surfaces can see which scopes dominate slow hands-on resolution
tails even when the overall median looks fine.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    summarize_case_handling_latency_histogram_by_entity_kind,
)


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/product/sku-1/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-handle-ek-1",
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


def _handle(
    store: InMemoryOperationalCaseStore,
    *,
    detection: OperationalCaseDetection,
    opened_at: datetime,
    acknowledged_at: datetime,
    resolved_at: datetime,
) -> str:
    case = store.upsert_detection(detection, detected_at=opened_at)
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=acknowledged_at,
    )
    store.transition_case(
        case.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=resolved_at,
    )
    return case.case_id


def test_handling_latency_histogram_by_entity_kind_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_handling_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result == {
        "business_id": "artemea",
        "handled_total": 0,
        "by_handling_bucket": _empty_buckets(),
        "by_handling_bucket_entity_kind": {bucket: {} for bucket in _empty_buckets()},
        "fastest_handled": None,
        "slowest_handled": None,
    }


def test_handling_latency_histogram_by_entity_kind_buckets_by_entity_kind():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    # (run_id, case_type, dedupe_suffix, entity_scope, ack_delay, resolve_delay)
    schedule = [
        (
            "a",
            "stockout_risk",
            "stockout_risk/product/sku-a/commerce.inventory/daily",
            {"kind": "product", "id": "sku-a", "label": "SKU A"},
            timedelta(hours=1),
            timedelta(hours=1, minutes=30),  # handling = 30m -> under_1h
        ),
        (
            "b",
            "sales_drop",
            "sales_drop/channel/all/commerce.revenue/daily",
            {"kind": "channel", "id": "all", "label": "Todos"},
            timedelta(hours=2),
            timedelta(hours=6),  # handling = 4h -> under_6h
        ),
        (
            "c",
            "sales_drop",
            "sales_drop/channel/meta_ads/commerce.revenue/daily",
            {"kind": "channel", "id": "meta_ads", "label": "Meta Ads"},
            timedelta(hours=1),
            timedelta(hours=11),  # handling = 10h -> under_24h
        ),
        (
            "d",
            "unanswered_conversations",
            "unanswered_conversations/conversation/wa-99/support.conversations/daily",
            {"kind": "conversation", "id": "wa-99", "label": "WA 99"},
            timedelta(hours=1),
            timedelta(days=2, hours=1),  # handling = 2d -> under_7d
        ),
        (
            "e",
            "data_stale",
            "data_stale/business/monitored/observability.feeds/daily",
            {"kind": "business", "id": "monitored", "label": "Monitoreado"},
            timedelta(hours=1),
            timedelta(days=10, hours=1),  # handling = 10d -> over_7d
        ),
    ]
    for run_id, case_type, dedupe_suffix, entity_scope, ack_delay, resolve_delay in schedule:
        _handle(
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
            acknowledged_at=opened_at + ack_delay,
            resolved_at=opened_at + resolve_delay,
        )

    result = summarize_case_handling_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 5
    assert result["by_handling_bucket"] == {
        "under_1h": 1,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 1,
        "over_7d": 1,
    }
    assert result["by_handling_bucket_entity_kind"] == {
        "under_1h": {"product": 1},
        "under_6h": {"channel": 1},
        "under_24h": {"channel": 1},
        "under_7d": {"conversation": 1},
        "over_7d": {"business": 1},
    }
    fastest = result["fastest_handled"]
    slowest = result["slowest_handled"]
    assert fastest is not None and slowest is not None
    assert fastest["time_to_handle_seconds"] == int(timedelta(minutes=30).total_seconds())
    assert fastest["case_type"] == "stockout_risk"
    assert slowest["time_to_handle_seconds"] == int(timedelta(days=10).total_seconds())
    assert slowest["case_type"] == "data_stale"


def test_handling_latency_histogram_by_entity_kind_excludes_open_and_acknowledged_only_cases():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=3)

    # Open-only -> excluded.
    store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            run_id="run-open",
            entity_scope={"kind": "product", "id": "sku-open", "label": "SKU Open"},
        ),
        detected_at=opened_at,
    )

    # Acknowledged-only -> excluded: handling time isn't finalised.
    ack_only = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-ack-only",
            entity_scope={"kind": "channel", "id": "all", "label": "Todos"},
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        ack_only.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=opened_at + timedelta(hours=1),
    )

    # Fully handled -> counted, handling = 3h -> under_6h.
    handled_id = _handle(
        store,
        detection=_detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/conversation/wa-99/support.conversations/daily",
            severity="info",
            priority=40,
            run_id="run-handled",
            entity_scope={"kind": "conversation", "id": "wa-99", "label": "WA 99"},
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=1),
        resolved_at=opened_at + timedelta(hours=4),
    )

    result = summarize_case_handling_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_6h"] == 1
    assert result["by_handling_bucket_entity_kind"]["under_6h"] == {
        "conversation": 1,
    }
    assert result["fastest_handled"]["case_id"] == handled_id
    assert result["slowest_handled"]["case_id"] == handled_id


def test_handling_latency_histogram_by_entity_kind_groups_multiple_cases_per_bucket():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    schedule = [
        (
            "a1",
            "stockout_risk",
            "stockout_risk/product/sku-a/commerce.inventory/daily",
            {"kind": "product", "id": "sku-a", "label": "SKU A"},
            timedelta(hours=2),
            timedelta(hours=4),  # handling = 2h -> under_6h
        ),
        (
            "a2",
            "stockout_risk",
            "stockout_risk/product/sku-b/commerce.inventory/daily",
            {"kind": "product", "id": "sku-b", "label": "SKU B"},
            timedelta(hours=1),
            timedelta(hours=5),  # handling = 4h -> under_6h
        ),
        (
            "a3",
            "sales_drop",
            "sales_drop/channel/meta_ads/commerce.revenue/daily",
            {"kind": "channel", "id": "meta_ads", "label": "Meta Ads"},
            timedelta(hours=2),
            timedelta(hours=7),  # handling = 5h -> under_6h
        ),
        (
            "a4",
            "data_stale",
            "data_stale/business/monitored/observability.feeds/daily",
            {"kind": "business", "id": "monitored", "label": "Monitoreado"},
            timedelta(hours=1),
            timedelta(days=8, hours=1),  # handling = 8d -> over_7d
        ),
    ]
    for run_id, case_type, dedupe_suffix, entity_scope, ack_delay, resolve_delay in schedule:
        _handle(
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
            acknowledged_at=opened_at + ack_delay,
            resolved_at=opened_at + resolve_delay,
        )

    result = summarize_case_handling_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 4
    assert result["by_handling_bucket"] == {
        "under_1h": 0,
        "under_6h": 3,
        "under_24h": 0,
        "under_7d": 0,
        "over_7d": 1,
    }
    assert result["by_handling_bucket_entity_kind"]["under_6h"] == {
        "product": 2,
        "channel": 1,
    }
    assert result["by_handling_bucket_entity_kind"]["over_7d"] == {"business": 1}


def test_handling_latency_histogram_by_entity_kind_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=5)

    _handle(
        store,
        detection=_detection(
            business_id="artemea",
            run_id="run-a",
            entity_scope={"kind": "product", "id": "sku-a", "label": "SKU A"},
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=1),
        resolved_at=opened_at + timedelta(hours=3),  # handling = 2h -> under_6h
    )
    _handle(
        store,
        detection=_detection(
            business_id="other-shop",
            case_type="data_stale",
            dedupe_suffix="data_stale/business/monitored/observability.feeds/daily",
            severity="info",
            priority=40,
            run_id="run-other",
            entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=1),
        resolved_at=opened_at + timedelta(days=9),  # handling > 7d -> over_7d
    )

    result = summarize_case_handling_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_6h"] == 1
    assert result["by_handling_bucket"]["over_7d"] == 0
    assert result["by_handling_bucket_entity_kind"]["under_6h"] == {"product": 1}
    assert "business" not in result["by_handling_bucket_entity_kind"]["over_7d"]


def test_handling_latency_histogram_by_entity_kind_buckets_missing_kind_as_unknown():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=2)

    _handle(
        store,
        detection=_detection(
            case_type="data_stale",
            dedupe_suffix="data_stale/business/monitored/observability.feeds/daily",
            severity="info",
            priority=40,
            run_id="run-no-kind",
            entity_scope={"id": "unknown-entity", "label": "Sin tipo"},
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=1),
        resolved_at=opened_at + timedelta(hours=4),  # handling = 3h -> under_6h
    )

    result = summarize_case_handling_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_6h"] == 1
    assert result["by_handling_bucket_entity_kind"]["under_6h"] == {"unknown": 1}


def test_handling_latency_histogram_by_entity_kind_clamps_non_positive_handling_to_zero():
    # Defensive: resolved_at == acknowledged_at -> 0s handling, still bucketed.
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(hours=2)
    acknowledged_at = opened_at + timedelta(hours=1)

    _handle(
        store,
        detection=_detection(
            case_type="stockout_risk",
            run_id="run-zero",
            entity_scope={"kind": "product", "id": "sku-zero", "label": "SKU Zero"},
        ),
        opened_at=opened_at,
        acknowledged_at=acknowledged_at,
        resolved_at=acknowledged_at,
    )

    result = summarize_case_handling_latency_histogram_by_entity_kind(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_1h"] == 1
    assert result["by_handling_bucket_entity_kind"]["under_1h"] == {"product": 1}
    assert result["fastest_handled"]["time_to_handle_seconds"] == 0
    assert result["slowest_handled"]["time_to_handle_seconds"] == 0

"""Tests for the source-connector-split handling-latency histogram projection.

Handling latency = ``resolved_at - acknowledged_at`` (operator working
time). This projection mirrors
:func:`summarize_case_handling_latency_histogram` but groups each bucket
by source connector (tiendanube/google_sheets/csv/etc.) so operator
surfaces can see which connectors dominate slow hands-on resolution
tails even when the overall median looks fine.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    summarize_case_handling_latency_histogram_by_source_connector,
)


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/product/sku-1/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-handle-src-1",
    source: str = "tiendanube",
) -> OperationalCaseDetection:
    # _source_from_evidence_ref parses the host segment after evidence://,
    # so embedding ``source`` there exercises the same path used in production.
    evidence_ref = f"evidence://{source}/{business_id}/{run_id}/{case_type}"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "product", "id": "sku-1", "label": "SKU 1"},
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


def test_handling_latency_histogram_by_source_connector_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_handling_latency_histogram_by_source_connector(
        store, business_id="artemea"
    )

    assert result == {
        "business_id": "artemea",
        "handled_total": 0,
        "by_handling_bucket": _empty_buckets(),
        "by_handling_bucket_source_connector": {
            bucket: {} for bucket in _empty_buckets()
        },
        "fastest_handled": None,
        "slowest_handled": None,
    }


def test_handling_latency_histogram_by_source_connector_buckets_by_source():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    # (run_id, case_type, dedupe_suffix, source, ack_delay, resolve_delay)
    schedule = [
        (
            "a",
            "stockout_risk",
            "stockout_risk/product/sku-a/commerce.inventory/daily",
            "tiendanube",
            timedelta(hours=1),
            timedelta(hours=1, minutes=30),  # handling = 30m -> under_1h
        ),
        (
            "b",
            "sales_drop",
            "sales_drop/channel/all/commerce.revenue/daily",
            "google_sheets",
            timedelta(hours=2),
            timedelta(hours=6),  # handling = 4h -> under_6h
        ),
        (
            "c",
            "sales_drop",
            "sales_drop/channel/meta_ads/commerce.revenue/daily",
            "google_sheets",
            timedelta(hours=1),
            timedelta(hours=11),  # handling = 10h -> under_24h
        ),
        (
            "d",
            "unanswered_conversations",
            "unanswered_conversations/conversation/wa-99/support.conversations/daily",
            "csv",
            timedelta(hours=1),
            timedelta(days=2, hours=1),  # handling = 2d -> under_7d
        ),
        (
            "e",
            "data_stale",
            "data_stale/business/monitored/observability.feeds/daily",
            "tiendanube",
            timedelta(hours=1),
            timedelta(days=10, hours=1),  # handling = 10d -> over_7d
        ),
    ]
    for run_id, case_type, dedupe_suffix, source, ack_delay, resolve_delay in schedule:
        _handle(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity="warning",
                priority=70,
                run_id=f"run-{run_id}",
                source=source,
            ),
            opened_at=opened_at,
            acknowledged_at=opened_at + ack_delay,
            resolved_at=opened_at + resolve_delay,
        )

    result = summarize_case_handling_latency_histogram_by_source_connector(
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
    assert result["by_handling_bucket_source_connector"] == {
        "under_1h": {"tiendanube": 1},
        "under_6h": {"google_sheets": 1},
        "under_24h": {"google_sheets": 1},
        "under_7d": {"csv": 1},
        "over_7d": {"tiendanube": 1},
    }
    fastest = result["fastest_handled"]
    slowest = result["slowest_handled"]
    assert fastest is not None and slowest is not None
    assert fastest["time_to_handle_seconds"] == int(timedelta(minutes=30).total_seconds())
    assert fastest["case_type"] == "stockout_risk"
    assert slowest["time_to_handle_seconds"] == int(timedelta(days=10).total_seconds())
    assert slowest["case_type"] == "data_stale"


def test_handling_latency_histogram_by_source_connector_excludes_open_and_acknowledged_only_cases():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=3)

    # Open-only -> excluded.
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open", source="tiendanube"),
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
            source="google_sheets",
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
            source="csv",
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=1),
        resolved_at=opened_at + timedelta(hours=4),
    )

    result = summarize_case_handling_latency_histogram_by_source_connector(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_6h"] == 1
    assert result["by_handling_bucket_source_connector"]["under_6h"] == {"csv": 1}
    assert result["fastest_handled"]["case_id"] == handled_id
    assert result["slowest_handled"]["case_id"] == handled_id


def test_handling_latency_histogram_by_source_connector_groups_multiple_cases_per_bucket():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    schedule = [
        (
            "a1",
            "stockout_risk",
            "stockout_risk/product/sku-a/commerce.inventory/daily",
            "tiendanube",
            timedelta(hours=2),
            timedelta(hours=4),  # handling = 2h -> under_6h
        ),
        (
            "a2",
            "stockout_risk",
            "stockout_risk/product/sku-b/commerce.inventory/daily",
            "tiendanube",
            timedelta(hours=1),
            timedelta(hours=5),  # handling = 4h -> under_6h
        ),
        (
            "a3",
            "sales_drop",
            "sales_drop/channel/meta_ads/commerce.revenue/daily",
            "google_sheets",
            timedelta(hours=2),
            timedelta(hours=7),  # handling = 5h -> under_6h
        ),
        (
            "a4",
            "data_stale",
            "data_stale/business/monitored/observability.feeds/daily",
            "csv",
            timedelta(hours=1),
            timedelta(days=8, hours=1),  # handling = 8d -> over_7d
        ),
    ]
    for run_id, case_type, dedupe_suffix, source, ack_delay, resolve_delay in schedule:
        _handle(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity="warning",
                priority=70,
                run_id=f"run-{run_id}",
                source=source,
            ),
            opened_at=opened_at,
            acknowledged_at=opened_at + ack_delay,
            resolved_at=opened_at + resolve_delay,
        )

    result = summarize_case_handling_latency_histogram_by_source_connector(
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
    assert result["by_handling_bucket_source_connector"]["under_6h"] == {
        "tiendanube": 2,
        "google_sheets": 1,
    }
    assert result["by_handling_bucket_source_connector"]["over_7d"] == {"csv": 1}


def test_handling_latency_histogram_by_source_connector_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=5)

    _handle(
        store,
        detection=_detection(
            business_id="artemea",
            run_id="run-a",
            source="tiendanube",
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
            source="google_sheets",
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=1),
        resolved_at=opened_at + timedelta(days=9),  # handling > 7d -> over_7d
    )

    result = summarize_case_handling_latency_histogram_by_source_connector(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_6h"] == 1
    assert result["by_handling_bucket"]["over_7d"] == 0
    assert result["by_handling_bucket_source_connector"]["under_6h"] == {
        "tiendanube": 1,
    }
    assert (
        "google_sheets"
        not in result["by_handling_bucket_source_connector"]["over_7d"]
    )


def test_handling_latency_histogram_by_source_connector_buckets_missing_source_as_unknown():
    # A detection with no evidence_refs leaves the case with zero evidence
    # snapshots, so _source_connectors returns []. Such handled cases must
    # still be accounted for under the "unknown" bucket so totals never
    # silently drop.
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=2)

    detection = OperationalCaseDetection(
        business_id="artemea",
        case_type="data_stale",
        dedupe_key="artemea/data_stale/business/monitored/observability.feeds/daily",
        title="Caso sin evidencia",
        severity="info",
        priority_score=70,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[],
        run_id="run-no-source",
        artifact_refs=[],
    )
    case = store.upsert_detection(detection, detected_at=opened_at)
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        case.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=opened_at + timedelta(hours=4),  # handling = 3h -> under_6h
    )

    result = summarize_case_handling_latency_histogram_by_source_connector(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_6h"] == 1
    assert result["by_handling_bucket_source_connector"]["under_6h"] == {"unknown": 1}


def test_handling_latency_histogram_by_source_connector_uses_first_sorted_source_for_multi_source_cases():
    # Cases with evidence from multiple connectors attribute to the first
    # sorted source name — mirroring
    # summarize_case_resolution_latency_histogram_by_source_connector and
    # summarize_case_acknowledgment_latency_histogram_by_source_connector —
    # so bucket counts stay equal to the count of handled cases without
    # double-counting.
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=2)

    first_detection = _detection(
        dedupe_suffix="stockout_risk/product/sku-multi/commerce.inventory/daily",
        run_id="run-multi-1",
        source="tiendanube",
    )
    case = store.upsert_detection(first_detection, detected_at=opened_at)
    # Add a second evidence snapshot from a different source.
    second_detection = _detection(
        dedupe_suffix="stockout_risk/product/sku-multi/commerce.inventory/daily",
        run_id="run-multi-2",
        source="google_sheets",
    )
    store.upsert_detection(
        second_detection, detected_at=opened_at + timedelta(minutes=10)
    )
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        case.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=opened_at + timedelta(hours=4),  # handling = 3h -> under_6h
    )

    result = summarize_case_handling_latency_histogram_by_source_connector(
        store, business_id="artemea"
    )

    # sorted(["tiendanube", "google_sheets"]) -> "google_sheets" first.
    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_6h"] == 1
    assert result["by_handling_bucket_source_connector"]["under_6h"] == {
        "google_sheets": 1,
    }


def test_handling_latency_histogram_by_source_connector_clamps_non_positive_handling_to_zero():
    # Defensive: resolved_at == acknowledged_at -> 0s handling, still bucketed.
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(hours=2)
    acknowledged_at = opened_at + timedelta(hours=1)

    _handle(
        store,
        detection=_detection(
            case_type="stockout_risk",
            run_id="run-zero",
            source="tiendanube",
        ),
        opened_at=opened_at,
        acknowledged_at=acknowledged_at,
        resolved_at=acknowledged_at,
    )

    result = summarize_case_handling_latency_histogram_by_source_connector(
        store, business_id="artemea"
    )

    assert result["handled_total"] == 1
    assert result["by_handling_bucket"]["under_1h"] == 1
    assert result["by_handling_bucket_source_connector"]["under_1h"] == {
        "tiendanube": 1,
    }
    assert result["fastest_handled"]["time_to_handle_seconds"] == 0
    assert result["slowest_handled"]["time_to_handle_seconds"] == 0

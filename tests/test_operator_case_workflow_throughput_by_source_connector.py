"""Tests for the source-connector-split case workflow throughput projection."""

from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import summarize_case_workflow_throughput_by_source_connector


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/product/sku-1/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-throughput-source-1",
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


def test_summarize_case_workflow_throughput_by_source_connector_returns_empty_summary_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_workflow_throughput_by_source_connector(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "total": 0,
        "totals_by_source_connector": {},
        "acknowledged_by_source_connector": {},
        "resolved_by_source_connector": {},
        "time_to_acknowledge_seconds_by_source_connector": {},
        "time_to_resolve_seconds_by_source_connector": {},
    }


def test_summarize_case_workflow_throughput_by_source_connector_splits_latencies_per_source():
    store = InMemoryOperationalCaseStore()
    # tiendanube A: opened 08:00, acknowledged 11:00, resolved 12:00.
    a = store.upsert_detection(
        _detection(
            dedupe_suffix="stockout_risk/product/sku-a/commerce.inventory/daily",
            run_id="run-a",
            source="tiendanube",
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
        transitioned_at=_utc(12),
    )
    # google_sheets B: opened 08:00, acknowledged 13:00, resolved 18:00.
    b = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-b",
            source="google_sheets",
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
        transitioned_at=_utc(18),
    )
    # tiendanube C: opened 08:00, acknowledged 09:00 only.
    c = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/meta_ads/commerce.revenue/daily",
            severity="warning",
            priority=65,
            run_id="run-c",
            source="tiendanube",
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
    # google_sheets D: opened 08:00 and still open — counts toward totals only.
    store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/product/sku-d/support.conversations/daily",
            severity="warning",
            priority=60,
            run_id="run-d",
            source="google_sheets",
        ),
        detected_at=_utc(8),
    )

    result = summarize_case_workflow_throughput_by_source_connector(store, business_id="artemea")

    assert result["business_id"] == "artemea"
    assert result["total"] == 4
    assert result["totals_by_source_connector"] == {
        "tiendanube": 2,
        "google_sheets": 2,
    }
    assert result["acknowledged_by_source_connector"] == {
        "tiendanube": 2,
        "google_sheets": 1,
    }
    assert result["resolved_by_source_connector"] == {
        "tiendanube": 1,
        "google_sheets": 1,
    }
    # tiendanube ack: [3h, 1h] -> [10800, 3600]. google_sheets ack: [5h] -> [18000].
    assert result["time_to_acknowledge_seconds_by_source_connector"] == {
        "tiendanube": {
            "min": 3600,
            "max": 10800,
            "avg": 7200,
            "median": 7200,
        },
        "google_sheets": {
            "min": 18000,
            "max": 18000,
            "avg": 18000,
            "median": 18000,
        },
    }
    # tiendanube resolve: 4h, google_sheets resolve: 10h.
    assert result["time_to_resolve_seconds_by_source_connector"] == {
        "tiendanube": {
            "min": 14400,
            "max": 14400,
            "avg": 14400,
            "median": 14400,
        },
        "google_sheets": {
            "min": 36000,
            "max": 36000,
            "avg": 36000,
            "median": 36000,
        },
    }


def test_summarize_case_workflow_throughput_by_source_connector_buckets_missing_source_as_unknown():
    # A detection with no evidence_refs leaves the case with zero evidence
    # snapshots, so _source_connectors returns []. Such cases must still be
    # accounted for under the "unknown" bucket so totals never silently drop.
    store = InMemoryOperationalCaseStore()
    detection = OperationalCaseDetection(
        business_id="artemea",
        case_type="stockout_risk",
        dedupe_key="artemea/stockout_risk/product/sku-x/commerce.inventory/daily",
        title="Caso sin evidencia",
        severity="critical",
        priority_score=90,
        entity_scope={"kind": "product", "id": "sku-x", "label": "SKU X"},
        evidence_refs=[],
        run_id="run-x",
        artifact_refs=[],
    )
    a = store.upsert_detection(detection, detected_at=_utc(8))
    store.transition_case(
        a.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(10),
    )

    result = summarize_case_workflow_throughput_by_source_connector(store, business_id="artemea")

    assert result["totals_by_source_connector"] == {"unknown": 1}
    assert result["acknowledged_by_source_connector"] == {"unknown": 1}
    assert result["time_to_acknowledge_seconds_by_source_connector"] == {
        "unknown": {
            "min": 7200,
            "max": 7200,
            "avg": 7200,
            "median": 7200,
        }
    }


def test_summarize_case_workflow_throughput_by_source_connector_uses_first_sorted_source_for_multi_source_cases():
    # Cases with evidence from multiple connectors attribute to the first
    # sorted source name. _source_connectors already returns a sorted list,
    # so this keeps totals exactly equal to len(cases) without double-counting.
    store = InMemoryOperationalCaseStore()
    first_detection = _detection(
        dedupe_suffix="stockout_risk/product/sku-multi/commerce.inventory/daily",
        run_id="run-multi-1",
        source="tiendanube",
    )
    multi = store.upsert_detection(first_detection, detected_at=_utc(8))
    # Second detection on the same dedupe_key brings a different source so
    # the case ends up with both "tiendanube" and "google_sheets" snapshots.
    second_detection = _detection(
        dedupe_suffix="stockout_risk/product/sku-multi/commerce.inventory/daily",
        run_id="run-multi-2",
        source="google_sheets",
    )
    store.upsert_detection(second_detection, detected_at=_utc(9))
    store.transition_case(
        multi.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=_utc(12),
    )

    result = summarize_case_workflow_throughput_by_source_connector(store, business_id="artemea")

    # sorted(["tiendanube", "google_sheets"]) -> "google_sheets" first.
    assert result["total"] == 1
    assert result["totals_by_source_connector"] == {"google_sheets": 1}
    assert result["acknowledged_by_source_connector"] == {"google_sheets": 1}
    assert result["time_to_acknowledge_seconds_by_source_connector"] == {
        "google_sheets": {
            "min": 14400,
            "max": 14400,
            "avg": 14400,
            "median": 14400,
        }
    }


def test_summarize_case_workflow_throughput_by_source_connector_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    a = store.upsert_detection(
        _detection(
            business_id="artemea",
            run_id="run-a",
            source="tiendanube",
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
            source="google_sheets",
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

    result = summarize_case_workflow_throughput_by_source_connector(store, business_id="artemea")

    assert result["total"] == 1
    assert result["totals_by_source_connector"] == {"tiendanube": 1}
    assert result["acknowledged_by_source_connector"] == {"tiendanube": 1}
    assert result["resolved_by_source_connector"] == {}
    assert result["time_to_acknowledge_seconds_by_source_connector"] == {
        "tiendanube": {
            "min": 7200,
            "max": 7200,
            "avg": 7200,
            "median": 7200,
        }
    }
    assert result["time_to_resolve_seconds_by_source_connector"] == {}

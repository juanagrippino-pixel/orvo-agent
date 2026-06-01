"""Tests for the case-type-split acknowledgment-latency histogram projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    summarize_case_acknowledgment_latency_histogram_by_case_type,
)


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-ack-ct-1",
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
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


def test_acknowledgment_latency_histogram_by_case_type_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_acknowledgment_latency_histogram_by_case_type(
        store, business_id="artemea"
    )

    assert result == {
        "business_id": "artemea",
        "acknowledged_total": 0,
        "by_acknowledgment_bucket": _empty_buckets(),
        "by_acknowledgment_bucket_case_type": {bucket: {} for bucket in _empty_buckets()},
        "fastest_acknowledged": None,
        "slowest_acknowledged": None,
    }


def test_acknowledgment_latency_histogram_by_case_type_buckets_by_case_type():
    store = InMemoryOperationalCaseStore()

    schedule = [
        ("a", "stockout_risk", "stockout_risk/business/monitored/commerce.inventory/daily", "critical", timedelta(minutes=30)),
        ("b", "sales_drop", "sales_drop/channel/all/commerce.revenue/daily", "warning", timedelta(hours=3)),
        ("c", "sales_drop", "sales_drop/channel/meta_ads/commerce.revenue/daily", "warning", timedelta(hours=10)),
        ("d", "unanswered_conversations", "unanswered_conversations/channel/whatsapp/support.conversations/daily", "warning", timedelta(days=2)),
        ("e", "data_stale", "data_stale/business/monitored/observability.feeds/daily", "info", timedelta(days=10)),
    ]
    for run_id, case_type, dedupe_suffix, severity, tta in schedule:
        opened_at = NOW - timedelta(days=30)
        _acknowledge(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity=severity,
                priority=70,
                run_id=f"run-{run_id}",
            ),
            opened_at=opened_at,
            acknowledged_at=opened_at + tta,
        )

    result = summarize_case_acknowledgment_latency_histogram_by_case_type(
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
    assert result["by_acknowledgment_bucket_case_type"] == {
        "under_1h": {"stockout_risk": 1},
        "under_6h": {"sales_drop": 1},
        "under_24h": {"sales_drop": 1},
        "under_7d": {"unanswered_conversations": 1},
        "over_7d": {"data_stale": 1},
    }
    fastest = result["fastest_acknowledged"]
    slowest = result["slowest_acknowledged"]
    assert fastest is not None and slowest is not None
    assert fastest["time_to_acknowledge_seconds"] == int(timedelta(minutes=30).total_seconds())
    assert fastest["case_type"] == "stockout_risk"
    assert slowest["time_to_acknowledge_seconds"] == int(timedelta(days=10).total_seconds())
    assert slowest["case_type"] == "data_stale"


def test_acknowledgment_latency_histogram_by_case_type_excludes_open_only_cases():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=3)

    # Open-only case — must be excluded.
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open"),
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
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=4),
    )

    result = summarize_case_acknowledgment_latency_histogram_by_case_type(
        store, business_id="artemea"
    )

    assert result["acknowledged_total"] == 1
    assert result["by_acknowledgment_bucket"]["under_6h"] == 1
    assert result["by_acknowledgment_bucket"]["under_1h"] == 0
    assert result["by_acknowledgment_bucket_case_type"]["under_6h"] == {
        "sales_drop": 1,
    }
    assert result["fastest_acknowledged"]["case_id"] == ack_id
    assert result["slowest_acknowledged"]["case_id"] == ack_id


def test_acknowledgment_latency_histogram_by_case_type_includes_resolved_cases():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=3)

    case = store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/support.conversations/daily",
            severity="warning",
            priority=70,
            run_id="run-resolved",
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

    result = summarize_case_acknowledgment_latency_histogram_by_case_type(
        store, business_id="artemea"
    )

    assert result["acknowledged_total"] == 1
    assert result["by_acknowledgment_bucket"]["under_6h"] == 1
    assert result["by_acknowledgment_bucket_case_type"]["under_6h"] == {
        "unanswered_conversations": 1,
    }


def test_acknowledgment_latency_histogram_by_case_type_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=5)

    _acknowledge(
        store,
        detection=_detection(business_id="artemea", run_id="run-a"),
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
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(days=8),
    )

    result = summarize_case_acknowledgment_latency_histogram_by_case_type(
        store, business_id="artemea"
    )

    assert result["acknowledged_total"] == 1
    assert result["by_acknowledgment_bucket"]["under_6h"] == 1
    assert result["by_acknowledgment_bucket"]["over_7d"] == 0
    assert result["by_acknowledgment_bucket_case_type"]["under_6h"] == {
        "stockout_risk": 1,
    }
    assert "data_stale" not in result["by_acknowledgment_bucket_case_type"]["over_7d"]


def test_acknowledgment_latency_histogram_by_case_type_groups_multiple_cases_per_bucket():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    schedule = [
        ("a1", "stockout_risk", "stockout_risk/business/monitored/commerce.inventory/daily", "critical", timedelta(hours=2)),
        ("a2", "sales_drop", "sales_drop/channel/all/commerce.revenue/daily", "warning", timedelta(hours=4)),
        ("a3", "sales_drop", "sales_drop/channel/meta_ads/commerce.revenue/daily", "warning", timedelta(hours=5)),
        ("a4", "data_stale", "data_stale/business/monitored/observability.feeds/daily", "info", timedelta(days=8)),
    ]
    for run_id, case_type, dedupe_suffix, severity, tta in schedule:
        _acknowledge(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity=severity,
                priority=70,
                run_id=f"run-{run_id}",
            ),
            opened_at=opened_at,
            acknowledged_at=opened_at + tta,
        )

    result = summarize_case_acknowledgment_latency_histogram_by_case_type(
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
    assert result["by_acknowledgment_bucket_case_type"]["under_6h"] == {
        "stockout_risk": 1,
        "sales_drop": 2,
    }
    assert result["by_acknowledgment_bucket_case_type"]["over_7d"] == {"data_stale": 1}

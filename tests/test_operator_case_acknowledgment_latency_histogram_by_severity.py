"""Tests for the severity-split acknowledgment-latency histogram projection.

Acknowledgment latency = ``acknowledged_at - opened_at`` (queue-wait leg).
This projection mirrors
:func:`summarize_case_acknowledgment_latency_histogram_by_priority_bracket`
but groups each bucket by case severity (info / warning / critical) instead
of priority bracket, matching the attribution used by
:func:`summarize_case_resolution_latency_histogram_by_severity`. Operator
surfaces use it to spot when long-tail first-touch latency is concentrated
in critical cases even though the overall median, case_type, entity_kind,
source-connector and priority-bracket distributions look healthy.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    summarize_case_acknowledgment_latency_histogram_by_severity,
)


NOW = datetime(2026, 6, 13, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-ack-sev-1",
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


def test_acknowledgment_latency_histogram_by_severity_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_acknowledgment_latency_histogram_by_severity(
        store, business_id="artemea"
    )

    assert result == {
        "business_id": "artemea",
        "acknowledged_total": 0,
        "by_acknowledgment_bucket": _empty_buckets(),
        "by_acknowledgment_bucket_severity": {bucket: {} for bucket in _empty_buckets()},
        "fastest_acknowledged": None,
        "slowest_acknowledged": None,
    }


def test_acknowledgment_latency_histogram_by_severity_buckets_by_severity():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    # (run_id, case_type, dedupe_suffix, severity, tta)
    schedule = [
        (
            "a",
            "stockout_risk",
            "stockout_risk/product/sku-a/commerce.inventory/daily",
            "critical",
            timedelta(minutes=30),  # under_1h
        ),
        (
            "b",
            "sales_drop",
            "sales_drop/channel/all/commerce.revenue/daily",
            "warning",
            timedelta(hours=3),  # under_6h
        ),
        (
            "c",
            "sales_drop",
            "sales_drop/channel/meta_ads/commerce.revenue/daily",
            "warning",
            timedelta(hours=10),  # under_24h
        ),
        (
            "d",
            "unanswered_conversations",
            "unanswered_conversations/conversation/wa-99/support.conversations/daily",
            "info",
            timedelta(days=2),  # under_7d
        ),
        (
            "e",
            "data_stale",
            "data_stale/business/monitored/observability.feeds/daily",
            "critical",
            timedelta(days=10),  # over_7d
        ),
    ]
    for run_id, case_type, dedupe_suffix, severity, tta in schedule:
        _acknowledge(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity=severity,
                run_id=f"run-{run_id}",
            ),
            opened_at=opened_at,
            acknowledged_at=opened_at + tta,
        )

    result = summarize_case_acknowledgment_latency_histogram_by_severity(
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
    assert result["by_acknowledgment_bucket_severity"] == {
        "under_1h": {"critical": 1},
        "under_6h": {"warning": 1},
        "under_24h": {"warning": 1},
        "under_7d": {"info": 1},
        "over_7d": {"critical": 1},
    }
    fastest = result["fastest_acknowledged"]
    slowest = result["slowest_acknowledged"]
    assert fastest is not None and slowest is not None
    assert fastest["time_to_acknowledge_seconds"] == int(timedelta(minutes=30).total_seconds())
    assert fastest["case_type"] == "stockout_risk"
    assert slowest["time_to_acknowledge_seconds"] == int(timedelta(days=10).total_seconds())
    assert slowest["case_type"] == "data_stale"


def test_acknowledgment_latency_histogram_by_severity_counts_resolved_cases():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=3)

    # Open-only case -> excluded (never acknowledged).
    store.upsert_detection(
        _detection(case_type="stockout_risk", severity="critical", run_id="run-open"),
        detected_at=opened_at,
    )

    # Acknowledged-then-resolved -> still counted on the ack leg, info severity.
    detection = _detection(
        case_type="unanswered_conversations",
        dedupe_suffix="unanswered_conversations/conversation/wa-99/support.conversations/daily",
        severity="info",
        priority=30,
        run_id="run-resolved",
    )
    case = store.upsert_detection(detection, detected_at=opened_at)
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=opened_at + timedelta(hours=4),  # under_6h
    )
    store.transition_case(
        case.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=opened_at + timedelta(hours=20),
    )

    result = summarize_case_acknowledgment_latency_histogram_by_severity(
        store, business_id="artemea"
    )

    assert result["acknowledged_total"] == 1
    assert result["by_acknowledgment_bucket"]["under_6h"] == 1
    assert result["by_acknowledgment_bucket_severity"]["under_6h"] == {"info": 1}
    assert result["fastest_acknowledged"]["case_id"] == case.case_id
    assert result["slowest_acknowledged"]["case_id"] == case.case_id


def test_acknowledgment_latency_histogram_by_severity_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=5)

    _acknowledge(
        store,
        detection=_detection(
            business_id="artemea",
            severity="critical",
            run_id="run-a",
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(hours=2),  # under_6h -> critical
    )
    _acknowledge(
        store,
        detection=_detection(
            business_id="other-shop",
            case_type="data_stale",
            dedupe_suffix="data_stale/business/monitored/observability.feeds/daily",
            severity="info",
            priority=20,
            run_id="run-other",
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at + timedelta(days=9),  # over_7d -> info
    )

    result = summarize_case_acknowledgment_latency_histogram_by_severity(
        store, business_id="artemea"
    )

    assert result["acknowledged_total"] == 1
    assert result["by_acknowledgment_bucket"]["under_6h"] == 1
    assert result["by_acknowledgment_bucket"]["over_7d"] == 0
    assert result["by_acknowledgment_bucket_severity"]["under_6h"] == {"critical": 1}
    assert "info" not in result["by_acknowledgment_bucket_severity"]["over_7d"]


def test_acknowledgment_latency_histogram_by_severity_groups_multiple_cases_per_bucket():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    schedule = [
        (
            "a1",
            "stockout_risk",
            "stockout_risk/product/sku-a/commerce.inventory/daily",
            "critical",
            timedelta(hours=2),  # under_6h
        ),
        (
            "a2",
            "stockout_risk",
            "stockout_risk/product/sku-b/commerce.inventory/daily",
            "critical",
            timedelta(hours=4),  # under_6h
        ),
        (
            "a3",
            "sales_drop",
            "sales_drop/channel/meta_ads/commerce.revenue/daily",
            "warning",
            timedelta(hours=5),  # under_6h
        ),
        (
            "a4",
            "data_stale",
            "data_stale/business/monitored/observability.feeds/daily",
            "info",
            timedelta(days=8),  # over_7d
        ),
    ]
    for run_id, case_type, dedupe_suffix, severity, tta in schedule:
        _acknowledge(
            store,
            detection=_detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity=severity,
                run_id=f"run-{run_id}",
            ),
            opened_at=opened_at,
            acknowledged_at=opened_at + tta,
        )

    result = summarize_case_acknowledgment_latency_histogram_by_severity(
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
    assert result["by_acknowledgment_bucket_severity"]["under_6h"] == {
        "critical": 2,
        "warning": 1,
    }
    assert result["by_acknowledgment_bucket_severity"]["over_7d"] == {"info": 1}


def test_acknowledgment_latency_histogram_by_severity_clamps_non_positive_latency_to_zero():
    # Defensive: acknowledged_at == opened_at -> 0s tta, still bucketed.
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(hours=2)

    _acknowledge(
        store,
        detection=_detection(
            case_type="stockout_risk",
            severity="critical",
            run_id="run-zero",
        ),
        opened_at=opened_at,
        acknowledged_at=opened_at,
    )

    result = summarize_case_acknowledgment_latency_histogram_by_severity(
        store, business_id="artemea"
    )

    assert result["acknowledged_total"] == 1
    assert result["by_acknowledgment_bucket"]["under_1h"] == 1
    assert result["by_acknowledgment_bucket_severity"]["under_1h"] == {"critical": 1}
    assert result["fastest_acknowledged"]["time_to_acknowledge_seconds"] == 0
    assert result["slowest_acknowledged"]["time_to_acknowledge_seconds"] == 0

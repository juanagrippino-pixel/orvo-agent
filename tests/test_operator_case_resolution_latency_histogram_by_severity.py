"""Tests for the explicit severity-split resolution-latency projection contract."""

from __future__ import annotations

from datetime import timedelta

from app.brain.operational_cases import InMemoryOperationalCaseStore
from app.brain.operator_api import summarize_case_resolution_latency_histogram_by_severity
from tests.test_operator_case_resolution_latency_histogram import NOW, _detection, _empty_buckets, _resolve


def test_summarize_case_resolution_latency_histogram_by_severity_returns_empty_summary():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_resolution_latency_histogram_by_severity(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "resolved_total": 0,
        "by_resolution_bucket": _empty_buckets(),
        "by_resolution_bucket_severity": {bucket: {} for bucket in _empty_buckets()},
        "fastest_resolved": None,
        "slowest_resolved": None,
    }


def test_summarize_case_resolution_latency_histogram_by_severity_splits_resolved_cases_by_severity():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=30)

    critical_id = _resolve(
        store,
        detection=_detection(
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/critical/commerce.inventory/daily",
            severity="critical",
            run_id="run-critical-severity-latency",
        ),
        opened_at=opened_at,
        resolved_at=opened_at + timedelta(hours=2),
    )
    _resolve(
        store,
        detection=_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-warning-severity-latency",
        ),
        opened_at=opened_at,
        resolved_at=opened_at + timedelta(hours=4),
    )
    _resolve(
        store,
        detection=_detection(
            case_type="data_stale",
            dedupe_suffix="data_stale/business/all/observability.feeds/daily",
            severity="info",
            priority=30,
            run_id="run-info-severity-latency",
        ),
        opened_at=opened_at,
        resolved_at=opened_at + timedelta(days=8),
    )
    store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/open/commerce.inventory/daily",
            severity="critical",
            run_id="run-open-severity-latency",
        ),
        detected_at=opened_at,
    )

    result = summarize_case_resolution_latency_histogram_by_severity(store, business_id="artemea")

    assert result["resolved_total"] == 3
    assert result["by_resolution_bucket"] == {
        "under_1h": 0,
        "under_6h": 2,
        "under_24h": 0,
        "under_7d": 0,
        "over_7d": 1,
    }
    assert result["by_resolution_bucket_severity"] == {
        "under_1h": {},
        "under_6h": {"critical": 1, "warning": 1},
        "under_24h": {},
        "under_7d": {},
        "over_7d": {"info": 1},
    }
    assert result["fastest_resolved"]["case_id"] == critical_id
    assert result["fastest_resolved"]["severity"] == "critical"

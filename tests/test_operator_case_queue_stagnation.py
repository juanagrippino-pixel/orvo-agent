"""Tests for the deterministic case-queue stagnation (idleness) projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import OperatorAPIError, summarize_case_queue_stagnation


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-stagnation-1",
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


def test_summarize_case_queue_stagnation_returns_empty_summary_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_queue_stagnation(store, business_id="artemea", now=NOW)

    assert result == {
        "business_id": "artemea",
        "now": "2026-05-26T12:00:00+00:00",
        "actionable_total": 0,
        "by_idle_bucket": _empty_buckets(),
        "by_idle_bucket_severity": {bucket: {} for bucket in _empty_buckets()},
        "most_stalled_actionable": None,
    }


def test_summarize_case_queue_stagnation_buckets_actionable_cases_by_idle_seconds():
    store = InMemoryOperationalCaseStore()

    # Spread of idleness relative to NOW. updated_at == opened_at at detection
    # time, so the detection age also drives the idleness bucket here.
    schedule = [
        ("a", "stockout_risk", "stockout_risk/business/monitored/commerce.inventory/daily", "critical", timedelta(minutes=30)),       # under_1h
        ("b", "sales_drop", "sales_drop/channel/all/commerce.revenue/daily", "warning", timedelta(hours=3)),                            # under_6h
        ("c", "sales_drop", "sales_drop/channel/meta_ads/commerce.revenue/daily", "warning", timedelta(hours=10)),                      # under_24h
        ("d", "unanswered_conversations", "unanswered_conversations/channel/whatsapp/support.conversations/daily", "warning", timedelta(days=2)),  # under_7d
        ("e", "data_stale", "data_stale/business/monitored/observability.feeds/daily", "info", timedelta(days=10)),                     # over_7d
    ]
    for run_id, case_type, dedupe_suffix, severity, age in schedule:
        store.upsert_detection(
            _detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity=severity,
                priority=70,
                run_id=f"run-{run_id}",
            ),
            detected_at=NOW - age,
        )

    result = summarize_case_queue_stagnation(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 5
    assert result["by_idle_bucket"] == {
        "under_1h": 1,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 1,
        "over_7d": 1,
    }
    assert result["by_idle_bucket_severity"] == {
        "under_1h": {"critical": 1},
        "under_6h": {"warning": 1},
        "under_24h": {"warning": 1},
        "under_7d": {"warning": 1},
        "over_7d": {"info": 1},
    }
    most_stalled = result["most_stalled_actionable"]
    assert most_stalled is not None
    assert most_stalled["idle_seconds"] == int(timedelta(days=10).total_seconds())
    assert most_stalled["age_seconds"] == int(timedelta(days=10).total_seconds())
    assert most_stalled["updated_at"] == (NOW - timedelta(days=10)).isoformat()
    assert most_stalled["opened_at"] == (NOW - timedelta(days=10)).isoformat()
    assert most_stalled["case_type"] == "data_stale"
    assert most_stalled["severity"] == "info"
    assert isinstance(most_stalled["case_id"], str) and most_stalled["case_id"]


def test_summarize_case_queue_stagnation_uses_updated_at_not_opened_at():
    """A recently-acknowledged old case should bucket by ack time, not opened_at."""
    store = InMemoryOperationalCaseStore()

    # Case opened a week ago, then acknowledged 30 minutes ago -> idle under_1h.
    moved = store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-moved"),
        detected_at=NOW - timedelta(days=7),
    )
    store.transition_case(
        moved.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(minutes=30),
    )

    # Case opened 2 days ago, never touched -> idle under_7d.
    untouched = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            run_id="run-untouched",
        ),
        detected_at=NOW - timedelta(days=2),
    )

    result = summarize_case_queue_stagnation(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 2
    assert result["by_idle_bucket"]["under_1h"] == 1
    assert result["by_idle_bucket"]["under_7d"] == 1
    assert result["by_idle_bucket"]["over_7d"] == 0
    # Severity splits track idleness bucket, not age.
    assert result["by_idle_bucket_severity"]["under_1h"] == {"critical": 1}
    assert result["by_idle_bucket_severity"]["under_7d"] == {"warning": 1}
    most_stalled = result["most_stalled_actionable"]
    assert most_stalled["case_id"] == untouched.case_id
    assert most_stalled["idle_seconds"] == int(timedelta(days=2).total_seconds())
    assert most_stalled["age_seconds"] == int(timedelta(days=2).total_seconds())


def test_summarize_case_queue_stagnation_excludes_resolved_cases():
    store = InMemoryOperationalCaseStore()
    open_case = store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open"),
        detected_at=NOW - timedelta(hours=2),
    )
    resolved = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-done",
        ),
        detected_at=NOW - timedelta(days=20),
    )
    store.transition_case(
        resolved.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(days=19),
    )
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(days=18),
    )

    result = summarize_case_queue_stagnation(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 1
    assert result["by_idle_bucket"]["under_6h"] == 1
    assert result["by_idle_bucket"]["over_7d"] == 0
    assert result["most_stalled_actionable"]["case_id"] == open_case.case_id


def test_summarize_case_queue_stagnation_includes_acknowledged_as_actionable():
    store = InMemoryOperationalCaseStore()
    case = store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-ack"),
        detected_at=NOW - timedelta(hours=8),
    )
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=3),
    )

    result = summarize_case_queue_stagnation(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 1
    # Bucket is based on updated_at (ack time), not opened_at.
    assert result["by_idle_bucket"]["under_6h"] == 1
    assert result["by_idle_bucket"]["under_24h"] == 0
    assert result["by_idle_bucket_severity"]["under_6h"] == {"critical": 1}
    most_stalled = result["most_stalled_actionable"]
    assert most_stalled["case_id"] == case.case_id
    assert most_stalled["status"] == "acknowledged"
    assert most_stalled["idle_seconds"] == int(timedelta(hours=3).total_seconds())
    assert most_stalled["age_seconds"] == int(timedelta(hours=8).total_seconds())


def test_summarize_case_queue_stagnation_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    store.upsert_detection(
        _detection(business_id="artemea", run_id="run-a"),
        detected_at=NOW - timedelta(hours=4),
    )
    store.upsert_detection(
        _detection(business_id="other-shop", run_id="run-other"),
        detected_at=NOW - timedelta(days=30),
    )

    result = summarize_case_queue_stagnation(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 1
    assert result["by_idle_bucket"]["under_6h"] == 1
    assert result["by_idle_bucket"]["over_7d"] == 0
    assert result["most_stalled_actionable"]["idle_seconds"] == int(timedelta(hours=4).total_seconds())


def test_summarize_case_queue_stagnation_uses_current_utc_when_now_not_provided(monkeypatch):
    store = InMemoryOperationalCaseStore()
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-now"),
        detected_at=NOW - timedelta(minutes=10),
    )

    import app.brain.operator_api as operator_api

    monkeypatch.setattr(operator_api, "_now_utc", lambda: NOW)

    result = summarize_case_queue_stagnation(store, business_id="artemea")

    assert result["now"] == "2026-05-26T12:00:00+00:00"
    assert result["actionable_total"] == 1
    assert result["by_idle_bucket"]["under_1h"] == 1


def test_summarize_case_queue_stagnation_rejects_naive_now():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        summarize_case_queue_stagnation(
            store,
            business_id="artemea",
            now=datetime(2026, 5, 26, 12),
        )

    assert exc_info.value.code == "invalid_now"
    assert exc_info.value.status_code == 400

"""Tests for the case-type-split case workflow throughput projection."""

from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import summarize_case_workflow_throughput_by_case_type


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-throughput-type-1",
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


def test_summarize_case_workflow_throughput_by_case_type_returns_empty_summary_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_workflow_throughput_by_case_type(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "total": 0,
        "totals_by_case_type": {},
        "acknowledged_by_case_type": {},
        "resolved_by_case_type": {},
        "time_to_acknowledge_seconds_by_case_type": {},
        "time_to_resolve_seconds_by_case_type": {},
    }


def test_summarize_case_workflow_throughput_by_case_type_splits_latencies_per_case_type():
    store = InMemoryOperationalCaseStore()
    # stockout_risk A: opened 08:00, acknowledged 11:00, resolved 12:00.
    a = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/monitored/commerce.inventory/daily",
            run_id="run-a",
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
    # sales_drop B: opened 08:00, acknowledged 13:00, resolved 18:00.
    b = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-b",
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
    # sales_drop C: opened 08:00, acknowledged 09:00 only.
    c = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/meta_ads/commerce.revenue/daily",
            severity="warning",
            priority=65,
            run_id="run-c",
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
    # unanswered_conversations D: opened 08:00 and still open — counts toward
    # totals only.
    store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/support.conversations/daily",
            severity="warning",
            priority=60,
            run_id="run-d",
        ),
        detected_at=_utc(8),
    )

    result = summarize_case_workflow_throughput_by_case_type(store, business_id="artemea")

    assert result["business_id"] == "artemea"
    assert result["total"] == 4
    assert result["totals_by_case_type"] == {
        "stockout_risk": 1,
        "sales_drop": 2,
        "unanswered_conversations": 1,
    }
    assert result["acknowledged_by_case_type"] == {
        "stockout_risk": 1,
        "sales_drop": 2,
    }
    assert result["resolved_by_case_type"] == {
        "stockout_risk": 1,
        "sales_drop": 1,
    }
    # stockout_risk ack: [3h] -> [10800]. sales_drop ack: [1h, 5h] -> [3600, 18000].
    assert result["time_to_acknowledge_seconds_by_case_type"] == {
        "stockout_risk": {
            "min": 10800,
            "max": 10800,
            "avg": 10800,
            "median": 10800,
        },
        "sales_drop": {
            "min": 3600,
            "max": 18000,
            "avg": 10800,
            "median": 10800,
        },
    }
    # stockout_risk resolve: [4h] -> [14400]. sales_drop resolve: [10h] -> [36000].
    assert result["time_to_resolve_seconds_by_case_type"] == {
        "stockout_risk": {
            "min": 14400,
            "max": 14400,
            "avg": 14400,
            "median": 14400,
        },
        "sales_drop": {
            "min": 36000,
            "max": 36000,
            "avg": 36000,
            "median": 36000,
        },
    }


def test_summarize_case_workflow_throughput_by_case_type_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    a = store.upsert_detection(
        _detection(
            business_id="artemea",
            case_type="stockout_risk",
            run_id="run-a",
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

    result = summarize_case_workflow_throughput_by_case_type(store, business_id="artemea")

    assert result["total"] == 1
    assert result["totals_by_case_type"] == {"stockout_risk": 1}
    assert result["acknowledged_by_case_type"] == {"stockout_risk": 1}
    assert result["resolved_by_case_type"] == {}
    assert result["time_to_acknowledge_seconds_by_case_type"] == {
        "stockout_risk": {
            "min": 7200,
            "max": 7200,
            "avg": 7200,
            "median": 7200,
        }
    }
    assert result["time_to_resolve_seconds_by_case_type"] == {}

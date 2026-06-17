"""Tests for deterministic ordering in case detail projections."""

from __future__ import annotations

from datetime import datetime, timezone

from app.brain.operational_cases import InMemoryOperationalCaseStore, OperationalCaseDetection
from app.brain.operator_api import case_detail


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(*, business_id: str = "artemea", run_id: str = "run-case-detail-1") -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type="stockout_risk",
        dedupe_key=f"{business_id}/stockout_risk/business/monitored/commerce.inventory/daily",
        title="Stock crítico",
        severity="critical",
        priority_score=100,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[f"evidence://{business_id}/{run_id}/stockout_risk"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        metadata={"source": "test"},
    )


def test_case_detail_reorders_out_of_order_timeline_events_chronologically():
    store = InMemoryOperationalCaseStore()
    case = store.upsert_detection(_detection(run_id="run-1"), detected_at=_utc(8))
    store.add_comment(
        case.case_id,
        actor_type="operator",
        actor_ref="operator@example.com",
        comment="Reviewing supplier",
        commented_at=_utc(10),
    )
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Picked up",
        transitioned_at=_utc(11),
    )
    reloaded = store.get_case(case.case_id)
    assert reloaded is not None
    reloaded.timeline = [
        reloaded.timeline[1],
        reloaded.timeline[0],
        reloaded.timeline[2],
    ]

    detail = case_detail(reloaded)

    assert [event["created_at"] for event in detail["timeline"]] == [
        _utc(8).isoformat().replace("+00:00", "Z"),
        _utc(10).isoformat().replace("+00:00", "Z"),
        _utc(11).isoformat().replace("+00:00", "Z"),
    ]
    assert [event["event_type"] for event in detail["timeline"]] == [
        "case_opened",
        "operator_comment",
        "status_changed",
    ]

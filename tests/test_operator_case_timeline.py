"""Tests for the scoped, filterable case timeline projection helper."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import OperatorAPIError, list_case_timeline


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _detection(*, business_id: str = "artemea", run_id: str = "run-timeline-1") -> OperationalCaseDetection:
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


def _seed_full_lifecycle() -> tuple[InMemoryOperationalCaseStore, str]:
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(_detection(run_id="run-1"), detected_at=_utc(8))
    store.upsert_detection(_detection(run_id="run-2"), detected_at=_utc(9))
    store.add_comment(
        opened.case_id,
        actor_type="operator",
        actor_ref="operator@example.com",
        comment="Reviewing supplier",
        commented_at=_utc(10),
    )
    store.transition_case(
        opened.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Picked up",
        transitioned_at=_utc(11),
    )
    store.transition_case(
        opened.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Restocked",
        transitioned_at=_utc(12),
    )
    return store, opened.case_id


def test_list_case_timeline_returns_full_chronological_timeline_with_metadata():
    store, case_id = _seed_full_lifecycle()

    result = list_case_timeline(store, business_id="artemea", case_id=case_id)

    assert result["case_id"] == case_id
    assert result["case_status"] == "resolved"
    assert result["filters"] == {"event_type": None, "actor_type": None}
    assert result["total"] == 5
    assert result["count"] == 5
    event_types = [event["event_type"] for event in result["events"]]
    assert event_types == [
        "case_opened",
        "case_updated",
        "operator_comment",
        "status_changed",
        "status_changed",
    ]
    assert all(event["case_id"] == case_id for event in result["events"])


def test_list_case_timeline_filters_by_event_type():
    store, case_id = _seed_full_lifecycle()

    result = list_case_timeline(
        store,
        business_id="artemea",
        case_id=case_id,
        event_type="status_changed",
    )

    assert result["filters"]["event_type"] == "status_changed"
    assert result["count"] == 2
    assert result["total"] == 2
    assert all(event["event_type"] == "status_changed" for event in result["events"])


def test_list_case_timeline_filters_by_actor_type_and_excludes_system_events():
    store, case_id = _seed_full_lifecycle()

    result = list_case_timeline(
        store,
        business_id="artemea",
        case_id=case_id,
        actor_type="operator",
    )

    assert result["filters"]["actor_type"] == "operator"
    assert result["count"] == 3
    assert {event["event_type"] for event in result["events"]} == {"operator_comment", "status_changed"}
    assert all(event["actor_type"] == "operator" for event in result["events"])


def test_list_case_timeline_limits_to_most_recent_events_in_chronological_order():
    store, case_id = _seed_full_lifecycle()

    result = list_case_timeline(store, business_id="artemea", case_id=case_id, limit="2")

    assert result["limit"] == 2
    assert result["total"] == 5
    assert result["count"] == 2
    assert [event["event_type"] for event in result["events"]] == ["status_changed", "status_changed"]


def test_list_case_timeline_rejects_invalid_event_type():
    store, case_id = _seed_full_lifecycle()

    with pytest.raises(OperatorAPIError) as exc:
        list_case_timeline(store, business_id="artemea", case_id=case_id, event_type="not_a_real_event")

    assert exc.value.code == "invalid_timeline_event_type"
    assert exc.value.status_code == 400


def test_list_case_timeline_rejects_invalid_actor_type():
    store, case_id = _seed_full_lifecycle()

    with pytest.raises(OperatorAPIError) as exc:
        list_case_timeline(store, business_id="artemea", case_id=case_id, actor_type="robot")

    assert exc.value.code == "invalid_timeline_actor_type"
    assert exc.value.status_code == 400


def test_list_case_timeline_rejects_cross_business_case_lookup():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(_detection(business_id="artemea"), detected_at=_utc(8))

    with pytest.raises(OperatorAPIError) as exc:
        list_case_timeline(store, business_id="other", case_id=opened.case_id)

    assert exc.value.code == "case_not_found"
    assert exc.value.status_code == 404


def test_list_case_timeline_redacts_secrets_in_actor_and_summary():
    store = InMemoryOperationalCaseStore()
    opened = store.upsert_detection(_detection(), detected_at=_utc(8))
    store.add_comment(
        opened.case_id,
        actor_type="operator",
        actor_ref="operator access_token=raw_timeline_secret",
        comment="Looked at api_key=raw_timeline_secret",
        commented_at=_utc(9),
    )

    result: dict[str, Any] = list_case_timeline(store, business_id="artemea", case_id=opened.case_id)

    serialized = str(result)
    assert "raw_timeline_secret" not in serialized
    comment_event = result["events"][-1]
    assert comment_event["actor_ref"] == "operator access_token=[REDACTED]"
    assert "[REDACTED]" in comment_event["summary"]

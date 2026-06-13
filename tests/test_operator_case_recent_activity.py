"""Tests for the shared recent case activity projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import InMemoryOperationalCaseStore, OperationalCaseDetection
from app.brain.operator_api import OperatorAPIError, list_recent_case_activity


NOW = datetime(2026, 6, 13, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-recent-1",
) -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso access_token=raw_title_secret",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored"},
        evidence_refs=[f"evidence://{business_id}/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def test_defaults_to_recently_updated_projection():
    store = InMemoryOperationalCaseStore()
    case = store.upsert_detection(
        _detection(dedupe_suffix="recent-activity/default-updated", run_id="run-updated"),
        detected_at=NOW - timedelta(days=1),
    )
    store.add_comment(
        case.case_id,
        actor_type="operator",
        actor_ref="operator access_token=raw_actor_secret",
        comment="seguimiento access_token=raw_comment_secret",
        commented_at=NOW - timedelta(minutes=5),
    )

    result = list_recent_case_activity(store, business_id="artemea")

    assert result["projection_type"] == "recent_case_activity"
    assert result["activity_type"] == "updated"
    assert result["total"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == case.case_id
    assert result["cases"][0]["latest_activity_type"] == "operator_comment"
    serialized = str(result)
    assert "raw_actor_secret" not in serialized
    assert "raw_comment_secret" not in serialized


def test_accepts_hyphenated_in_progress_activity_type():
    store = InMemoryOperationalCaseStore()
    case = store.upsert_detection(
        _detection(dedupe_suffix="recent-activity/in-progress", run_id="run-progress"),
        detected_at=NOW - timedelta(hours=6),
    )
    store.transition_case(
        case.case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=1),
    )

    result = list_recent_case_activity(store, business_id="artemea", activity_type="in-progress")

    assert result["activity_type"] == "in_progress"
    assert result["total"] == 1
    assert result["cases"][0]["case_id"] == case.case_id
    assert result["cases"][0]["status"] == "in_progress"
    assert result["cases"][0]["time_to_in_progress_seconds"] > 0


def test_rejects_unsupported_recent_activity_type():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        list_recent_case_activity(store, business_id="artemea", activity_type="api_key=raw_secret")

    assert exc_info.value.code == "invalid_recent_activity_type"
    assert exc_info.value.status_code == 400
    assert "raw_secret" not in exc_info.value.message

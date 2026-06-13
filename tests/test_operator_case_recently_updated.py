"""Tests for the deterministic recently-updated cases projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import InMemoryOperationalCaseStore, OperationalCaseDetection
from app.brain.operator_api import OperatorAPIError, list_recently_updated_cases


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-updated-1",
) -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso access_token=raw_title_secret",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado access_token=raw_entity_secret"},
        evidence_refs=[f"evidence://{business_id}/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def _comment(
    store: InMemoryOperationalCaseStore,
    case_id: str,
    *,
    comment: str,
    commented_at: datetime,
    actor_ref: str = "operator@example.com",
) -> None:
    store.add_comment(
        case_id,
        actor_type="operator",
        actor_ref=actor_ref,
        comment=comment,
        commented_at=commented_at,
    )


def test_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = list_recently_updated_cases(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "projection_type": "recent_case_activity",
        "activity_type": "updated",
        "total": 0,
        "updated_total": 0,
        "cases": [],
        "limit": 50,
        "count": 0,
    }


def test_orders_by_latest_canonical_timeline_event_and_redacts_boundary_fields():
    store = InMemoryOperationalCaseStore()
    opened_only = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/opened/commerce.revenue/daily",
            severity="warning",
            priority=70,
            run_id="run-opened",
        ),
        detected_at=NOW - timedelta(days=2),
    )
    commented = store.upsert_detection(
        _detection(run_id="run-commented", dedupe_suffix="updated/commented"),
        detected_at=NOW - timedelta(days=3),
    )
    _comment(
        store,
        commented.case_id,
        comment="follow-up access_token=raw_comment_secret",
        actor_ref="operator access_token=raw_actor_secret",
        commented_at=NOW - timedelta(minutes=20),
    )
    resolved = store.upsert_detection(
        _detection(run_id="run-resolved", dedupe_suffix="updated/resolved"),
        detected_at=NOW - timedelta(days=4),
    )
    store.transition_case(
        resolved.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=2),
    )
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator access_token=raw_resolution_actor_secret",
        reason="done access_token=raw_reason_secret",
        transitioned_at=NOW - timedelta(minutes=5),
    )

    result = list_recently_updated_cases(store, business_id="artemea")

    assert result["updated_total"] == 3
    assert result["count"] == 3
    assert [entry["case_id"] for entry in result["cases"]] == [
        resolved.case_id,
        commented.case_id,
        opened_only.case_id,
    ]
    first = result["cases"][0]
    assert first["status"] == "resolved"
    assert first["case_type"] == "stockout_risk"
    assert first["title"] == "Caso access_token=[REDACTED]"
    assert first["entity_scope"] == {
        "kind": "business",
        "id": "monitored",
        "label": "Monitoreado access_token=[REDACTED]",
    }
    assert first["latest_activity_type"] == "status_changed"
    assert first["latest_activity_at"] == (NOW - timedelta(minutes=5)).isoformat()
    assert first["latest_activity_summary"] == "done access_token=[REDACTED]"
    assert first["latest_activity_actor_type"] == "operator"
    assert first["latest_activity_actor_ref"] == "operator access_token=[REDACTED]"
    assert first["timeline_event_count"] == 3
    serialized = str(result)
    assert "raw_title_secret" not in serialized
    assert "raw_entity_secret" not in serialized
    assert "raw_comment_secret" not in serialized
    assert "raw_actor_secret" not in serialized
    assert "raw_reason_secret" not in serialized
    assert "raw_resolution_actor_secret" not in serialized


def test_respects_limit_scopes_business_and_tiebreaks_on_case_id():
    store = InMemoryOperationalCaseStore()
    case_ids: list[str] = []
    for suffix in ("alpha", "beta", "gamma"):
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/{suffix}/commerce.revenue/daily",
                severity="warning",
                run_id=f"run-{suffix}",
            ),
            detected_at=NOW,
        )
        case_ids.append(case.case_id)
    other_business = store.upsert_detection(
        _detection(
            business_id="other-shop",
            run_id="run-other",
            dedupe_suffix="updated/other",
        ),
        detected_at=NOW + timedelta(minutes=1),
    )

    result = list_recently_updated_cases(store, business_id="artemea", limit="2")

    assert result["updated_total"] == 3
    assert result["limit"] == 2
    assert result["count"] == 2
    assert [entry["case_id"] for entry in result["cases"]] == sorted(case_ids)[:2]
    returned_case_ids = {entry["case_id"] for entry in result["cases"]}
    assert other_business.case_id not in returned_case_ids


def test_rejects_invalid_limit():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        list_recently_updated_cases(store, business_id="artemea", limit="not-an-int")

    assert exc_info.value.code == "invalid_limit"
    assert exc_info.value.status_code == 400

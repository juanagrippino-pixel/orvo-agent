"""Tests for the deterministic recently-dismissed cases projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import InMemoryOperationalCaseStore, OperationalCaseDetection
from app.brain.operator_api import OperatorAPIError, list_recently_dismissed_cases


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-dismissed-1",
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso con api_key=raw_secret_title",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def _dismiss(
    store: InMemoryOperationalCaseStore,
    case_id: str,
    *,
    dismissed_at: datetime,
) -> None:
    store.transition_case(
        case_id,
        status="dismissed",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="No longer actionable after manual review.",
        transitioned_at=dismissed_at,
    )


def test_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = list_recently_dismissed_cases(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "dismissed_total": 0,
        "cases": [],
        "limit": 50,
        "count": 0,
    }


def test_orders_most_recently_dismissed_first_and_redacts_payload():
    store = InMemoryOperationalCaseStore()
    cases_by_run: dict[str, str] = {}
    for run_id, since_dismissed in [
        ("old", timedelta(days=2)),
        ("new", timedelta(hours=3)),
    ]:
        opened_at = NOW - since_dismissed - timedelta(hours=5)
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/{run_id}/commerce.revenue/daily",
                severity="warning",
                priority=70,
                run_id=f"run-{run_id}",
            ),
            detected_at=opened_at,
        )
        _dismiss(store, case.case_id, dismissed_at=NOW - since_dismissed)
        cases_by_run[run_id] = case.case_id

    result = list_recently_dismissed_cases(store, business_id="artemea")

    assert result["dismissed_total"] == 2
    assert result["count"] == 2
    assert [entry["case_id"] for entry in result["cases"]] == [cases_by_run["new"], cases_by_run["old"]]
    first = result["cases"][0]
    assert first["status"] == "dismissed"
    assert first["case_type"] == "sales_drop"
    assert first["dismissed_at"].startswith("2026-05-26T09:00:00")
    assert first["dismissal_seconds"] == int(timedelta(hours=5).total_seconds())
    assert "raw_secret_title" not in str(result)


def test_respects_limit_and_scopes_per_business():
    store = InMemoryOperationalCaseStore()
    mine_old = store.upsert_detection(
        _detection(run_id="run-mine-old", dedupe_suffix="stockout_risk/business/mine-old/commerce.inventory/daily"),
        detected_at=NOW - timedelta(days=3),
    )
    _dismiss(store, mine_old.case_id, dismissed_at=NOW - timedelta(days=2))
    mine_new = store.upsert_detection(
        _detection(run_id="run-mine-new", dedupe_suffix="stockout_risk/business/mine-new/commerce.inventory/daily"),
        detected_at=NOW - timedelta(days=2),
    )
    _dismiss(store, mine_new.case_id, dismissed_at=NOW - timedelta(hours=1))
    other = store.upsert_detection(
        _detection(business_id="other-shop", run_id="run-other"),
        detected_at=NOW - timedelta(days=1),
    )
    _dismiss(store, other.case_id, dismissed_at=NOW)

    result = list_recently_dismissed_cases(store, business_id="artemea", limit="1")

    assert result["limit"] == 1
    assert result["dismissed_total"] == 2
    assert result["count"] == 1
    assert [entry["case_id"] for entry in result["cases"]] == [mine_new.case_id]


def test_excludes_open_acknowledged_and_resolved_cases():
    store = InMemoryOperationalCaseStore()
    dismissed = store.upsert_detection(
        _detection(run_id="run-dismissed"),
        detected_at=NOW - timedelta(days=1),
    )
    _dismiss(store, dismissed.case_id, dismissed_at=NOW - timedelta(hours=1))
    store.upsert_detection(
        _detection(run_id="run-open", dedupe_suffix="stockout_risk/business/open/commerce.inventory/daily"),
        detected_at=NOW - timedelta(hours=2),
    )
    acknowledged = store.upsert_detection(
        _detection(run_id="run-ack", dedupe_suffix="stockout_risk/business/ack/commerce.inventory/daily"),
        detected_at=NOW - timedelta(hours=3),
    )
    store.transition_case(
        acknowledged.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=2),
    )
    resolved = store.upsert_detection(
        _detection(run_id="run-resolved", dedupe_suffix="stockout_risk/business/resolved/commerce.inventory/daily"),
        detected_at=NOW - timedelta(hours=4),
    )
    store.transition_case(
        resolved.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=3),
    )
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved in fixture.",
        transitioned_at=NOW - timedelta(hours=2),
    )

    result = list_recently_dismissed_cases(store, business_id="artemea")

    assert result["dismissed_total"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == dismissed.case_id


def test_tiebreaks_on_case_id():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=2)
    dismissed_at = NOW - timedelta(hours=6)
    case_ids: list[str] = []
    for suffix in ("alpha", "beta", "gamma"):
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/{suffix}/commerce.revenue/daily",
                severity="warning",
                run_id=f"run-{suffix}",
            ),
            detected_at=opened_at,
        )
        _dismiss(store, case.case_id, dismissed_at=dismissed_at)
        case_ids.append(case.case_id)

    result = list_recently_dismissed_cases(store, business_id="artemea")

    assert result["dismissed_total"] == 3
    assert [entry["case_id"] for entry in result["cases"]] == sorted(case_ids)
    assert all(entry["dismissed_at"] == dismissed_at.isoformat() for entry in result["cases"])


def test_rejects_invalid_limit():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        list_recently_dismissed_cases(store, business_id="artemea", limit="not-an-int")

    assert exc_info.value.code == "invalid_limit"
    assert exc_info.value.status_code == 400

"""Tests for the deterministic top-N actionable cases by age projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    OperatorAPIError,
    list_top_actionable_cases_by_age,
)


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-top-1",
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


def test_list_top_actionable_cases_by_age_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = list_top_actionable_cases_by_age(store, business_id="artemea", now=NOW)

    assert result == {
        "business_id": "artemea",
        "now": "2026-05-26T12:00:00+00:00",
        "actionable_total": 0,
        "cases": [],
        "limit": 50,
        "count": 0,
    }


def test_list_top_actionable_cases_by_age_orders_oldest_first():
    store = InMemoryOperationalCaseStore()

    schedule = [
        ("a", "stockout_risk", "stockout_risk/business/monitored/commerce.inventory/daily", "critical", timedelta(minutes=30)),
        ("b", "sales_drop", "sales_drop/channel/all/commerce.revenue/daily", "warning", timedelta(hours=3)),
        ("c", "sales_drop", "sales_drop/channel/meta_ads/commerce.revenue/daily", "warning", timedelta(hours=10)),
        ("d", "unanswered_conversations", "unanswered_conversations/channel/whatsapp/support.conversations/daily", "warning", timedelta(days=2)),
        ("e", "data_stale", "data_stale/business/monitored/observability.feeds/daily", "info", timedelta(days=10)),
    ]
    cases_by_run: dict[str, str] = {}
    for run_id, case_type, dedupe_suffix, severity, age in schedule:
        case = store.upsert_detection(
            _detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity=severity,
                priority=70,
                run_id=f"run-{run_id}",
            ),
            detected_at=NOW - age,
        )
        cases_by_run[run_id] = case.case_id

    result = list_top_actionable_cases_by_age(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 5
    assert result["count"] == 5
    ages = [entry["age_seconds"] for entry in result["cases"]]
    assert ages == sorted(ages, reverse=True)
    # Oldest is run-e (10 days), newest is run-a (30 min).
    assert result["cases"][0]["case_id"] == cases_by_run["e"]
    assert result["cases"][0]["case_type"] == "data_stale"
    assert result["cases"][0]["severity"] == "info"
    assert result["cases"][0]["age_seconds"] == int(timedelta(days=10).total_seconds())
    assert result["cases"][-1]["case_id"] == cases_by_run["a"]
    assert result["cases"][-1]["age_seconds"] == int(timedelta(minutes=30).total_seconds())


def test_list_top_actionable_cases_by_age_respects_limit():
    store = InMemoryOperationalCaseStore()

    schedule = [
        ("oldest", timedelta(days=5)),
        ("middle", timedelta(days=3)),
        ("newest", timedelta(hours=2)),
    ]
    cases_by_run: dict[str, str] = {}
    for index, (run_id, age) in enumerate(schedule):
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/c{index}/commerce.revenue/daily",
                severity="warning",
                run_id=f"run-{run_id}",
            ),
            detected_at=NOW - age,
        )
        cases_by_run[run_id] = case.case_id

    result = list_top_actionable_cases_by_age(
        store, business_id="artemea", now=NOW, limit="2"
    )

    assert result["limit"] == 2
    assert result["actionable_total"] == 3
    assert result["count"] == 2
    assert [entry["case_id"] for entry in result["cases"]] == [
        cases_by_run["oldest"],
        cases_by_run["middle"],
    ]


def test_list_top_actionable_cases_by_age_excludes_resolved_cases():
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

    result = list_top_actionable_cases_by_age(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == open_case.case_id
    assert result["cases"][0]["status"] == "open"


def test_list_top_actionable_cases_by_age_includes_acknowledged():
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
        transitioned_at=NOW - timedelta(hours=1),
    )

    result = list_top_actionable_cases_by_age(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 1
    assert result["cases"][0]["case_id"] == case.case_id
    assert result["cases"][0]["status"] == "acknowledged"
    # Age is computed from opened_at, not ack timestamp.
    assert result["cases"][0]["age_seconds"] == int(timedelta(hours=8).total_seconds())


def test_list_top_actionable_cases_by_age_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    mine = store.upsert_detection(
        _detection(business_id="artemea", run_id="run-mine"),
        detected_at=NOW - timedelta(hours=4),
    )
    store.upsert_detection(
        _detection(business_id="other-shop", run_id="run-other"),
        detected_at=NOW - timedelta(days=30),
    )

    result = list_top_actionable_cases_by_age(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == mine.case_id


def test_list_top_actionable_cases_by_age_tiebreaks_on_case_id():
    store = InMemoryOperationalCaseStore()
    detected_at = NOW - timedelta(hours=6)
    cases = []
    for suffix in ("alpha", "beta", "gamma"):
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/{suffix}/commerce.revenue/daily",
                severity="warning",
                run_id=f"run-{suffix}",
            ),
            detected_at=detected_at,
        )
        cases.append(case.case_id)

    result = list_top_actionable_cases_by_age(store, business_id="artemea", now=NOW)

    assert result["actionable_total"] == 3
    returned_ids = [entry["case_id"] for entry in result["cases"]]
    assert returned_ids == sorted(cases)
    # All same age, so tie-break is purely case_id ASC.
    assert all(
        entry["age_seconds"] == int(timedelta(hours=6).total_seconds())
        for entry in result["cases"]
    )


def test_list_top_actionable_cases_by_age_uses_current_utc_when_now_not_provided(monkeypatch):
    store = InMemoryOperationalCaseStore()
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-now"),
        detected_at=NOW - timedelta(minutes=10),
    )

    import app.brain.operator_api as operator_api

    monkeypatch.setattr(operator_api, "_now_utc", lambda: NOW)

    result = list_top_actionable_cases_by_age(store, business_id="artemea")

    assert result["now"] == "2026-05-26T12:00:00+00:00"
    assert result["actionable_total"] == 1
    assert result["cases"][0]["age_seconds"] == 600


def test_list_top_actionable_cases_by_age_rejects_naive_now():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        list_top_actionable_cases_by_age(
            store,
            business_id="artemea",
            now=datetime(2026, 5, 26, 12),
        )

    assert exc_info.value.code == "invalid_now"
    assert exc_info.value.status_code == 400


def test_list_top_actionable_cases_by_age_rejects_invalid_limit():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        list_top_actionable_cases_by_age(
            store, business_id="artemea", now=NOW, limit="not-an-int"
        )

    assert exc_info.value.code == "invalid_limit"
    assert exc_info.value.status_code == 400

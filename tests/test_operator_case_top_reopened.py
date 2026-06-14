"""Tests for the deterministic top-N reopened actionable cases projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    OperatorAPIError,
    list_top_reopened_cases,
)


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-reopen-top-1",
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


def _cycle_resolve_then_reopen(
    store: InMemoryOperationalCaseStore,
    case_id: str,
    *,
    acknowledged_at: datetime,
    resolved_at: datetime,
    reopened_at: datetime,
) -> None:
    store.transition_case(
        case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=acknowledged_at,
    )
    store.transition_case(
        case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved test fixture",
        transitioned_at=resolved_at,
    )
    store.reopen_case(
        case_id,
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Recurrió.",
        reopened_at=reopened_at,
    )


def _reopen_n_times(
    store: InMemoryOperationalCaseStore,
    case_id: str,
    *,
    first_open_at: datetime,
    times: int,
) -> datetime:
    """Drive the case through ``times`` resolve/reopen cycles.

    Returns the timestamp of the latest reopen so callers can assert on it.
    """

    cycle_at = first_open_at + timedelta(hours=1)
    latest_reopen_at = cycle_at
    for index in range(times):
        ack_at = cycle_at
        res_at = cycle_at + timedelta(hours=1)
        reopen_at = cycle_at + timedelta(hours=2)
        _cycle_resolve_then_reopen(
            store,
            case_id,
            acknowledged_at=ack_at,
            resolved_at=res_at,
            reopened_at=reopen_at,
        )
        latest_reopen_at = reopen_at
        cycle_at = reopen_at + timedelta(hours=1)
    return latest_reopen_at


def test_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = list_top_reopened_cases(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "reopened_total": 0,
        "cases": [],
        "limit": 50,
        "count": 0,
    }


def test_excludes_cases_never_reopened():
    store = InMemoryOperationalCaseStore()

    # Open but never resolved/reopened — excluded.
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open-only"),
        detected_at=NOW - timedelta(hours=4),
    )

    result = list_top_reopened_cases(store, business_id="artemea")

    assert result["reopened_total"] == 0
    assert result["count"] == 0
    assert result["cases"] == []


def test_orders_by_reopen_count_desc():
    store = InMemoryOperationalCaseStore()

    schedule = [
        ("a", "stockout_risk", "stockout_risk/business/monitored/commerce.inventory/daily", 1),
        ("b", "sales_drop", "sales_drop/channel/all/commerce.revenue/daily", 3),
        ("c", "sales_drop", "sales_drop/channel/meta_ads/commerce.revenue/daily", 2),
    ]
    cases_by_run: dict[str, str] = {}
    for run_id, case_type, dedupe_suffix, times in schedule:
        opened_at = NOW - timedelta(days=10)
        case = store.upsert_detection(
            _detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity="warning",
                run_id=f"run-{run_id}",
            ),
            detected_at=opened_at,
        )
        _reopen_n_times(
            store, case.case_id, first_open_at=opened_at, times=times
        )
        cases_by_run[run_id] = case.case_id

    result = list_top_reopened_cases(store, business_id="artemea")

    assert result["reopened_total"] == 3
    assert result["count"] == 3
    returned = [(entry["case_id"], entry["reopen_count"]) for entry in result["cases"]]
    assert returned == [
        (cases_by_run["b"], 3),
        (cases_by_run["c"], 2),
        (cases_by_run["a"], 1),
    ]
    # latest_reopened_at is the timestamp of the most recent case_reopened event.
    for entry in result["cases"]:
        assert "latest_reopened_at" in entry
        assert entry["latest_reopened_at"].startswith("2026-")


def test_includes_actionable_acknowledged_cases():
    store = InMemoryOperationalCaseStore()

    # Reopened then re-acknowledged — included because acknowledged is actionable.
    opened_at = NOW - timedelta(days=3)
    case = store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-reack"),
        detected_at=opened_at,
    )
    latest_reopen_at = _reopen_n_times(
        store, case.case_id, first_open_at=opened_at, times=2
    )
    # Re-acknowledge after the last reopen — stays actionable.
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=latest_reopen_at + timedelta(hours=1),
    )

    result = list_top_reopened_cases(store, business_id="artemea")

    assert result["reopened_total"] == 1
    assert result["count"] == 1
    entry = result["cases"][0]
    assert entry["case_id"] == case.case_id
    assert entry["status"] == "acknowledged"
    assert entry["reopen_count"] == 2
    assert entry["latest_reopened_at"] == latest_reopen_at.isoformat()


def test_excludes_terminal_resolved_and_cancelled_cases():
    store = InMemoryOperationalCaseStore()

    opened_at = NOW - timedelta(days=4)
    # Reopened twice then re-resolved — excluded; not currently actionable.
    case = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            run_id="run-reres",
        ),
        detected_at=opened_at,
    )
    latest_reopen_at = _reopen_n_times(
        store, case.case_id, first_open_at=opened_at, times=2
    )
    store.transition_case(
        case.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=latest_reopen_at + timedelta(hours=1),
    )
    store.transition_case(
        case.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved test fixture",
        transitioned_at=latest_reopen_at + timedelta(hours=2),
    )

    result = list_top_reopened_cases(store, business_id="artemea")

    assert result["reopened_total"] == 0
    assert result["count"] == 0


def test_tiebreaks_on_case_id_when_reopen_counts_equal():
    store = InMemoryOperationalCaseStore()

    case_ids: list[str] = []
    for suffix in ("alpha", "beta", "gamma"):
        opened_at = NOW - timedelta(days=3)
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/{suffix}/commerce.revenue/daily",
                severity="warning",
                run_id=f"run-{suffix}",
            ),
            detected_at=opened_at,
        )
        _reopen_n_times(store, case.case_id, first_open_at=opened_at, times=2)
        case_ids.append(case.case_id)

    result = list_top_reopened_cases(store, business_id="artemea")

    assert result["reopened_total"] == 3
    returned_ids = [entry["case_id"] for entry in result["cases"]]
    assert returned_ids == sorted(case_ids)
    assert all(entry["reopen_count"] == 2 for entry in result["cases"])


def test_respects_limit():
    store = InMemoryOperationalCaseStore()

    schedule = [("first", 1), ("second", 2), ("third", 3), ("fourth", 4)]
    cases_by_run: dict[str, str] = {}
    for index, (run_id, times) in enumerate(schedule):
        opened_at = NOW - timedelta(days=8)
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/c{index}/commerce.revenue/daily",
                severity="warning",
                run_id=f"run-{run_id}",
            ),
            detected_at=opened_at,
        )
        _reopen_n_times(store, case.case_id, first_open_at=opened_at, times=times)
        cases_by_run[run_id] = case.case_id

    result = list_top_reopened_cases(store, business_id="artemea", limit="2")

    assert result["limit"] == 2
    assert result["reopened_total"] == 4
    assert result["count"] == 2
    assert [entry["case_id"] for entry in result["cases"]] == [
        cases_by_run["fourth"],
        cases_by_run["third"],
    ]


def test_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()

    opened_at = NOW - timedelta(days=2)
    mine = store.upsert_detection(
        _detection(business_id="artemea", run_id="run-mine"),
        detected_at=opened_at,
    )
    _reopen_n_times(store, mine.case_id, first_open_at=opened_at, times=1)

    other = store.upsert_detection(
        _detection(business_id="other-shop", run_id="run-other"),
        detected_at=opened_at,
    )
    _reopen_n_times(store, other.case_id, first_open_at=opened_at, times=5)

    result = list_top_reopened_cases(store, business_id="artemea")

    assert result["reopened_total"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == mine.case_id
    assert result["cases"][0]["reopen_count"] == 1


def test_rejects_invalid_limit():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        list_top_reopened_cases(store, business_id="artemea", limit="not-an-int")

    assert exc_info.value.code == "invalid_limit"
    assert exc_info.value.status_code == 400

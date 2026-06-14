"""Tests for the severity-split case-reopen-count aggregate projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import summarize_case_reopen_counts_by_severity


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-reopen-sev-1",
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
        reason="Cerrado para simular recurrencia.",
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
    cycle_at = first_open_at + timedelta(hours=1)
    latest_reopen_at = cycle_at
    for _ in range(times):
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


def _empty_buckets() -> dict[str, int]:
    return {
        "none": 0,
        "once": 0,
        "twice": 0,
        "three_to_five": 0,
        "six_plus": 0,
    }


def test_returns_zero_totals_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_reopen_counts_by_severity(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "actionable_total": 0,
        "actionable_reopened_cases": 0,
        "actionable_total_reopens": 0,
        "actionable_max_reopen_count": 0,
        "by_severity": {},
    }


def test_groups_actionable_counts_and_buckets_by_severity():
    store = InMemoryOperationalCaseStore()

    # Critical: two actionable, one with 4 reopens, one fresh open.
    crit_opened = NOW - timedelta(days=10)
    crit_a = store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/monitored/commerce.inventory/daily",
            severity="critical",
            run_id="run-crit-a",
        ),
        detected_at=crit_opened,
    )
    _reopen_n_times(store, crit_a.case_id, first_open_at=crit_opened, times=4)
    store.upsert_detection(
        _detection(
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/business/other/commerce.inventory/daily",
            severity="critical",
            run_id="run-crit-b",
        ),
        detected_at=NOW - timedelta(hours=3),
    )

    # Warning: three actionable — 0, 2, and 7 reopens.
    warn_zero_opened = NOW - timedelta(hours=4)
    store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/c0/commerce.revenue/daily",
            severity="warning",
            run_id="run-warn-a",
        ),
        detected_at=warn_zero_opened,
    )
    warn_two_opened = NOW - timedelta(days=2)
    warn_two = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/c1/commerce.revenue/daily",
            severity="warning",
            run_id="run-warn-b",
        ),
        detected_at=warn_two_opened,
    )
    _reopen_n_times(store, warn_two.case_id, first_open_at=warn_two_opened, times=2)
    warn_seven_opened = NOW - timedelta(days=5)
    warn_seven = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/c2/commerce.revenue/daily",
            severity="warning",
            run_id="run-warn-c",
        ),
        detected_at=warn_seven_opened,
    )
    _reopen_n_times(store, warn_seven.case_id, first_open_at=warn_seven_opened, times=7)

    result = summarize_case_reopen_counts_by_severity(store, business_id="artemea")

    assert result["business_id"] == "artemea"
    assert result["actionable_total"] == 5
    assert result["actionable_reopened_cases"] == 3
    assert result["actionable_total_reopens"] == 4 + 2 + 7
    assert result["actionable_max_reopen_count"] == 7

    by_severity = result["by_severity"]
    assert set(by_severity) == {"critical", "warning"}

    critical = by_severity["critical"]
    assert critical["actionable_total"] == 2
    assert critical["actionable_reopened_cases"] == 1
    assert critical["actionable_total_reopens"] == 4
    assert critical["actionable_max_reopen_count"] == 4
    expected_crit = _empty_buckets()
    expected_crit["none"] = 1
    expected_crit["three_to_five"] = 1
    assert critical["by_reopen_bucket"] == expected_crit

    warning = by_severity["warning"]
    assert warning["actionable_total"] == 3
    assert warning["actionable_reopened_cases"] == 2
    assert warning["actionable_total_reopens"] == 9
    assert warning["actionable_max_reopen_count"] == 7
    expected_warn = _empty_buckets()
    expected_warn["none"] = 1
    expected_warn["twice"] = 1
    expected_warn["six_plus"] = 1
    assert warning["by_reopen_bucket"] == expected_warn


def test_excludes_terminal_resolved_and_cancelled_cases():
    store = InMemoryOperationalCaseStore()

    opened_at = NOW - timedelta(days=4)
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
        reason="Resuelto nuevamente.",
        transitioned_at=latest_reopen_at + timedelta(hours=2),
    )

    # Currently-actionable critical case with zero reopens — only severity present.
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open"),
        detected_at=NOW - timedelta(hours=2),
    )

    result = summarize_case_reopen_counts_by_severity(store, business_id="artemea")

    assert result["actionable_total"] == 1
    assert result["actionable_reopened_cases"] == 0
    assert result["actionable_total_reopens"] == 0
    assert result["actionable_max_reopen_count"] == 0
    assert set(result["by_severity"]) == {"critical"}
    critical = result["by_severity"]["critical"]
    assert critical["actionable_total"] == 1
    assert critical["actionable_reopened_cases"] == 0
    assert critical["by_reopen_bucket"]["none"] == 1


def test_includes_acknowledged_cases_in_actionable_counts():
    store = InMemoryOperationalCaseStore()

    opened_at = NOW - timedelta(days=3)
    case = store.upsert_detection(
        _detection(case_type="stockout_risk", severity="critical", run_id="run-reack"),
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

    result = summarize_case_reopen_counts_by_severity(store, business_id="artemea")

    assert result["actionable_total"] == 1
    assert result["actionable_reopened_cases"] == 1
    assert result["actionable_total_reopens"] == 2
    assert result["actionable_max_reopen_count"] == 2
    critical = result["by_severity"]["critical"]
    assert critical["actionable_total"] == 1
    assert critical["actionable_reopened_cases"] == 1
    assert critical["actionable_total_reopens"] == 2
    assert critical["actionable_max_reopen_count"] == 2
    assert critical["by_reopen_bucket"]["twice"] == 1


def test_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()

    opened_at = NOW - timedelta(days=2)
    mine = store.upsert_detection(
        _detection(business_id="artemea", severity="warning", run_id="run-mine"),
        detected_at=opened_at,
    )
    _reopen_n_times(store, mine.case_id, first_open_at=opened_at, times=1)

    other = store.upsert_detection(
        _detection(business_id="other-shop", severity="critical", run_id="run-other"),
        detected_at=opened_at,
    )
    _reopen_n_times(store, other.case_id, first_open_at=opened_at, times=5)

    result = summarize_case_reopen_counts_by_severity(store, business_id="artemea")

    assert result["actionable_total"] == 1
    assert result["actionable_reopened_cases"] == 1
    assert result["actionable_total_reopens"] == 1
    assert result["actionable_max_reopen_count"] == 1
    assert set(result["by_severity"]) == {"warning"}
    warning = result["by_severity"]["warning"]
    assert warning["actionable_total"] == 1
    assert warning["actionable_reopened_cases"] == 1
    assert warning["actionable_total_reopens"] == 1
    assert warning["actionable_max_reopen_count"] == 1
    assert warning["by_reopen_bucket"]["once"] == 1

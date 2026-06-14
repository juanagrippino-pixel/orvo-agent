"""Tests for the deterministic case-reopen-count aggregate projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import summarize_case_reopen_counts


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-reopen-counts-1",
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


def test_returns_zeros_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = summarize_case_reopen_counts(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "actionable_total": 0,
        "actionable_reopened_cases": 0,
        "actionable_total_reopens": 0,
        "actionable_max_reopen_count": 0,
        "by_reopen_bucket": _empty_buckets(),
    }


def test_counts_actionable_cases_without_reopens_in_none_bucket():
    store = InMemoryOperationalCaseStore()

    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open"),
        detected_at=NOW - timedelta(hours=4),
    )

    result = summarize_case_reopen_counts(store, business_id="artemea")

    assert result["actionable_total"] == 1
    assert result["actionable_reopened_cases"] == 0
    assert result["actionable_total_reopens"] == 0
    assert result["actionable_max_reopen_count"] == 0
    assert result["by_reopen_bucket"]["none"] == 1
    assert sum(result["by_reopen_bucket"].values()) == 1


def test_buckets_cases_by_reopen_count_tiers():
    store = InMemoryOperationalCaseStore()

    # Reopen-count plan: 0, 1, 2, 3, 4, 5, 6, 9
    schedule = [
        ("none-a", 0),
        ("once-a", 1),
        ("twice-a", 2),
        ("three-a", 3),
        ("four-a", 4),
        ("five-a", 5),
        ("six-a", 6),
        ("nine-a", 9),
    ]
    for index, (run_id, times) in enumerate(schedule):
        opened_at = NOW - timedelta(days=15)
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/c{index}/commerce.revenue/daily",
                severity="warning",
                run_id=f"run-{run_id}",
            ),
            detected_at=opened_at,
        )
        if times:
            _reopen_n_times(store, case.case_id, first_open_at=opened_at, times=times)

    result = summarize_case_reopen_counts(store, business_id="artemea")

    assert result["actionable_total"] == 8
    assert result["actionable_reopened_cases"] == 7
    assert result["actionable_total_reopens"] == 0 + 1 + 2 + 3 + 4 + 5 + 6 + 9
    assert result["actionable_max_reopen_count"] == 9
    assert result["by_reopen_bucket"] == {
        "none": 1,
        "once": 1,
        "twice": 1,
        "three_to_five": 3,
        "six_plus": 2,
    }


def test_includes_acknowledged_cases_in_actionable_counts():
    store = InMemoryOperationalCaseStore()

    opened_at = NOW - timedelta(days=3)
    case = store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-reack"),
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

    result = summarize_case_reopen_counts(store, business_id="artemea")

    assert result["actionable_total"] == 1
    assert result["actionable_reopened_cases"] == 1
    assert result["actionable_total_reopens"] == 2
    assert result["actionable_max_reopen_count"] == 2
    assert result["by_reopen_bucket"]["twice"] == 1


def test_excludes_terminal_resolved_and_cancelled_cases():
    store = InMemoryOperationalCaseStore()

    # Reopened twice then re-resolved — excluded from actionable counts.
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

    # Currently-actionable case with zero reopens — counts in `none` bucket.
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open"),
        detected_at=NOW - timedelta(hours=2),
    )

    result = summarize_case_reopen_counts(store, business_id="artemea")

    assert result["actionable_total"] == 1
    assert result["actionable_reopened_cases"] == 0
    assert result["actionable_total_reopens"] == 0
    assert result["actionable_max_reopen_count"] == 0
    assert result["by_reopen_bucket"]["none"] == 1


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

    result = summarize_case_reopen_counts(store, business_id="artemea")

    assert result["actionable_total"] == 1
    assert result["actionable_reopened_cases"] == 1
    assert result["actionable_total_reopens"] == 1
    assert result["actionable_max_reopen_count"] == 1
    assert result["by_reopen_bucket"]["once"] == 1
    assert result["by_reopen_bucket"]["three_to_five"] == 0

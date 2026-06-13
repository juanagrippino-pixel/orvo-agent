"""Tests for the deterministic recently-assigned cases projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import OperatorAPIError, list_recently_assigned_cases


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-assigned-1",
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso access_token=raw_title_secret",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def _assign(
    store: InMemoryOperationalCaseStore,
    case_id: str,
    *,
    assignee_ref: str = "owner@example.com",
    assigned_at: datetime,
) -> None:
    store.assign_case(
        case_id,
        actor_type="operator",
        actor_ref="operator@example.com",
        assignee_ref=assignee_ref,
        assigned_at=assigned_at,
    )


def test_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = list_recently_assigned_cases(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "projection_type": "recent_case_activity",
        "activity_type": "assigned",
        "total": 0,
        "assigned_total": 0,
        "cases": [],
        "limit": 50,
        "count": 0,
    }


def test_orders_most_recently_assigned_first_and_redacts_assignee():
    store = InMemoryOperationalCaseStore()
    schedule = [
        ("older", timedelta(days=2), "owner access_token=raw_old_secret"),
        ("newer", timedelta(hours=3), "owner access_token=raw_new_secret"),
        ("newest", timedelta(minutes=30), "owner access_token=raw_latest_secret"),
    ]
    cases_by_run: dict[str, str] = {}
    for index, (run_id, since_assigned, assignee_ref) in enumerate(schedule):
        opened_at = NOW - since_assigned - timedelta(hours=4)
        assigned_at = NOW - since_assigned
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/{index}/commerce.revenue/daily",
                severity="warning",
                priority=70,
                run_id=f"run-{run_id}",
            ),
            detected_at=opened_at,
        )
        _assign(store, case.case_id, assignee_ref=assignee_ref, assigned_at=assigned_at)
        cases_by_run[run_id] = case.case_id

    result = list_recently_assigned_cases(store, business_id="artemea")

    assert result["assigned_total"] == 3
    assert result["count"] == 3
    assert [entry["case_id"] for entry in result["cases"]] == [
        cases_by_run["newest"],
        cases_by_run["newer"],
        cases_by_run["older"],
    ]
    first = result["cases"][0]
    assert first["status"] == "open"
    assert first["case_type"] == "sales_drop"
    assert first["assigned_at"].startswith("2026-05-26T11:30:00")
    assert first["assignment_seconds"] == int(timedelta(hours=4).total_seconds())
    assert first["assignee_ref"] == "owner access_token=[REDACTED]"
    assert "raw_latest_secret" not in str(result)
    assert "raw_title_secret" not in str(result)


def test_respects_limit_excludes_unassigned_and_terminal_cases_and_scopes_business():
    store = InMemoryOperationalCaseStore()
    included_older = store.upsert_detection(
        _detection(
            run_id="run-included-older",
            dedupe_suffix="sales_drop/channel/included_older/commerce.revenue/daily",
            case_type="sales_drop",
            severity="warning",
        ),
        detected_at=NOW - timedelta(days=2),
    )
    _assign(store, included_older.case_id, assigned_at=NOW - timedelta(hours=6))
    included_newer = store.upsert_detection(
        _detection(
            run_id="run-included-newer",
            dedupe_suffix="sales_drop/channel/included_newer/commerce.revenue/daily",
            case_type="sales_drop",
            severity="warning",
        ),
        detected_at=NOW - timedelta(days=1),
    )
    _assign(store, included_newer.case_id, assigned_at=NOW - timedelta(hours=1))
    unassigned = store.upsert_detection(
        _detection(run_id="run-unassigned", dedupe_suffix="assigned/unassigned"),
        detected_at=NOW - timedelta(minutes=5),
    )
    terminal = store.upsert_detection(
        _detection(run_id="run-terminal", dedupe_suffix="assigned/terminal"),
        detected_at=NOW - timedelta(days=3),
    )
    _assign(store, terminal.case_id, assigned_at=NOW - timedelta(minutes=10))
    store.transition_case(
        terminal.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(minutes=2),
    )
    store.transition_case(
        terminal.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved",
        transitioned_at=NOW - timedelta(minutes=1),
    )
    other_business = store.upsert_detection(
        _detection(
            business_id="other-shop",
            run_id="run-other",
            dedupe_suffix="assigned/other",
        ),
        detected_at=NOW - timedelta(hours=2),
    )
    _assign(store, other_business.case_id, assigned_at=NOW - timedelta(minutes=2))

    result = list_recently_assigned_cases(store, business_id="artemea", limit="1")

    assert result["assigned_total"] == 2
    assert result["limit"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == included_newer.case_id
    returned_case_ids = {entry["case_id"] for entry in result["cases"]}
    assert included_older.case_id not in returned_case_ids
    assert unassigned.case_id not in returned_case_ids
    assert terminal.case_id not in returned_case_ids
    assert other_business.case_id not in returned_case_ids


def test_tiebreaks_on_case_id():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=2)
    assigned_at = NOW - timedelta(hours=6)
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
        _assign(store, case.case_id, assigned_at=assigned_at)
        case_ids.append(case.case_id)

    result = list_recently_assigned_cases(store, business_id="artemea")

    assert result["assigned_total"] == 3
    assert [entry["case_id"] for entry in result["cases"]] == sorted(case_ids)
    assert all(entry["assigned_at"] == assigned_at.isoformat() for entry in result["cases"])


def test_rejects_invalid_limit():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        list_recently_assigned_cases(store, business_id="artemea", limit="not-an-int")

    assert exc_info.value.code == "invalid_limit"
    assert exc_info.value.status_code == 400

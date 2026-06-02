"""Tests for the deterministic recently-reopened cases projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import InMemoryOperationalCaseStore, OperationalCaseDetection
from app.brain.operator_api import OperatorAPIError, list_recently_reopened_cases


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-reopened-1",
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso reabierto con api_key=raw_reopened_title_secret",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report?access_token=raw_reopened_artifact_secret"],
    )


def _resolve(
    store: InMemoryOperationalCaseStore,
    case_id: str,
    *,
    acknowledged_at: datetime,
    resolved_at: datetime,
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
        reason="Resolved before recurrence.",
        transitioned_at=resolved_at,
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
        reason="Dismissed before recurrence.",
        transitioned_at=dismissed_at,
    )


def _reopen(
    store: InMemoryOperationalCaseStore,
    *,
    business_id: str = "artemea",
    dedupe_suffix: str,
    run_id: str,
    reopened_at: datetime,
    from_status: str = "resolved",
):
    opened_at = reopened_at - timedelta(days=3)
    case = store.upsert_detection(
        _detection(
            business_id=business_id,
            dedupe_suffix=dedupe_suffix,
            run_id=f"run-original-{run_id}",
        ),
        detected_at=opened_at,
    )
    if from_status == "dismissed":
        _dismiss(store, case.case_id, dismissed_at=reopened_at - timedelta(days=1))
    else:
        _resolve(
            store,
            case.case_id,
            acknowledged_at=reopened_at - timedelta(days=2),
            resolved_at=reopened_at - timedelta(days=1),
        )
    return store.upsert_detection(
        _detection(
            business_id=business_id,
            dedupe_suffix=dedupe_suffix,
            run_id=run_id,
        ),
        detected_at=reopened_at,
    )


def test_returns_empty_when_no_reopened_cases():
    store = InMemoryOperationalCaseStore()

    result = list_recently_reopened_cases(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "reopened_total": 0,
        "cases": [],
        "limit": 50,
        "count": 0,
    }


def test_orders_recent_actionable_reopens_and_redacts_boundary():
    store = InMemoryOperationalCaseStore()
    old = _reopen(
        store,
        dedupe_suffix="recent/reopened/old",
        run_id="run-reopen-old",
        reopened_at=NOW - timedelta(days=1),
    )
    new = _reopen(
        store,
        dedupe_suffix="recent/reopened/new",
        run_id="run-reopen-new",
        reopened_at=NOW - timedelta(hours=1),
        from_status="dismissed",
    )
    never_reopened = store.upsert_detection(
        _detection(dedupe_suffix="recent/reopened/never", run_id="run-open"),
        detected_at=NOW,
    )
    terminal_again = _reopen(
        store,
        dedupe_suffix="recent/reopened/terminal",
        run_id="run-reopen-terminal",
        reopened_at=NOW - timedelta(minutes=30),
    )
    _resolve(
        store,
        terminal_again.case_id,
        acknowledged_at=NOW - timedelta(minutes=20),
        resolved_at=NOW - timedelta(minutes=10),
    )

    result = list_recently_reopened_cases(store, business_id="artemea")

    assert result["reopened_total"] == 2
    assert result["count"] == 2
    assert [entry["case_id"] for entry in result["cases"]] == [new.case_id, old.case_id]
    assert result["cases"][0]["status"] == "open"
    assert result["cases"][0]["reopened_at"].startswith("2026-05-26T11:00:00")
    assert result["cases"][0]["time_to_reopen_seconds"] == int(timedelta(days=3).total_seconds())
    assert never_reopened.case_id not in {entry["case_id"] for entry in result["cases"]}
    assert terminal_again.case_id not in {entry["case_id"] for entry in result["cases"]}
    assert "raw_reopened" not in str(result)


def test_respects_limit_scopes_business_and_tiebreaks_on_case_id():
    store = InMemoryOperationalCaseStore()
    same_time = NOW - timedelta(hours=1)
    mine_b = _reopen(
        store,
        dedupe_suffix="recent/reopened/zulu",
        run_id="run-zulu",
        reopened_at=same_time,
    )
    mine_a = _reopen(
        store,
        dedupe_suffix="recent/reopened/alpha",
        run_id="run-alpha",
        reopened_at=same_time,
    )
    other = _reopen(
        store,
        business_id="other-biz",
        dedupe_suffix="recent/reopened/other",
        run_id="run-other",
        reopened_at=NOW,
    )

    result = list_recently_reopened_cases(store, business_id="artemea", limit="1")

    assert result["reopened_total"] == 2
    assert result["limit"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == min(mine_a.case_id, mine_b.case_id)
    assert other.case_id not in {entry["case_id"] for entry in result["cases"]}


def test_rejects_invalid_limit():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        list_recently_reopened_cases(store, business_id="artemea", limit="not-an-int")

    assert exc_info.value.code == "invalid_limit"
    assert exc_info.value.status_code == 400

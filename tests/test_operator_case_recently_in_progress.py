"""Tests for the deterministic recently-in-progress cases projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    OperatorAPIError,
    list_recently_in_progress_cases,
)

NOW = datetime(2026, 6, 3, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-progress-1",
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


def _start_progress(
    store: InMemoryOperationalCaseStore,
    case_id: str,
    *,
    started_at: datetime,
) -> None:
    store.transition_case(
        case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=started_at,
    )


def test_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = list_recently_in_progress_cases(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "in_progress_total": 0,
        "cases": [],
        "limit": 50,
        "count": 0,
    }


def test_orders_most_recently_started_in_progress_first():
    store = InMemoryOperationalCaseStore()
    cases_by_run: dict[str, str] = {}

    for run_id, since_started in (
        ("old", timedelta(days=3)),
        ("middle", timedelta(hours=12)),
        ("new", timedelta(hours=1)),
    ):
        opened_at = NOW - since_started - timedelta(hours=5)
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
        _start_progress(store, case.case_id, started_at=NOW - since_started)
        cases_by_run[run_id] = case.case_id

    result = list_recently_in_progress_cases(store, business_id="artemea")

    assert result["in_progress_total"] == 3
    assert result["count"] == 3
    assert [entry["case_id"] for entry in result["cases"]] == [
        cases_by_run["new"],
        cases_by_run["middle"],
        cases_by_run["old"],
    ]
    first = result["cases"][0]
    assert first["status"] == "in_progress"
    assert first["in_progress_at"] == (NOW - timedelta(hours=1)).isoformat()
    assert first["time_to_in_progress_seconds"] == int(timedelta(hours=5).total_seconds())


def test_ties_on_in_progress_time_order_by_case_id():
    store = InMemoryOperationalCaseStore()
    first = store.upsert_detection(
        _detection(
            run_id="run-a",
            dedupe_suffix="stockout_risk/product/a/commerce.inventory/daily",
        ),
        detected_at=NOW - timedelta(hours=5),
    )
    second = store.upsert_detection(
        _detection(
            run_id="run-b",
            dedupe_suffix="stockout_risk/product/b/commerce.inventory/daily",
        ),
        detected_at=NOW - timedelta(hours=4),
    )
    _start_progress(store, second.case_id, started_at=NOW - timedelta(hours=1))
    _start_progress(store, first.case_id, started_at=NOW - timedelta(hours=1))

    result = list_recently_in_progress_cases(store, business_id="artemea")

    assert [entry["case_id"] for entry in result["cases"]] == sorted([first.case_id, second.case_id])


def test_uses_status_transition_time_not_later_comment_updated_at():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=1)
    started_at = NOW - timedelta(hours=8)
    case = store.upsert_detection(_detection(), detected_at=opened_at)
    _start_progress(store, case.case_id, started_at=started_at)
    store.add_comment(
        case.case_id,
        actor_type="operator",
        actor_ref="operator@example.com",
        comment="Seguimiento sin cambiar estado",
        commented_at=NOW - timedelta(minutes=5),
    )

    result = list_recently_in_progress_cases(store, business_id="artemea")

    assert result["in_progress_total"] == 1
    assert result["cases"][0]["in_progress_at"] == started_at.isoformat()
    assert result["cases"][0]["time_to_in_progress_seconds"] == int(
        (started_at - opened_at).total_seconds()
    )


def test_excludes_open_acknowledged_and_terminal_cases():
    store = InMemoryOperationalCaseStore()
    store.upsert_detection(_detection(run_id="run-open"), detected_at=NOW - timedelta(hours=3))

    acknowledged = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/ack/commerce.revenue/daily",
            severity="warning",
            run_id="run-ack",
        ),
        detected_at=NOW - timedelta(hours=4),
    )
    store.transition_case(
        acknowledged.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=3),
    )

    active = store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/support.conversations/daily",
            severity="warning",
            run_id="run-active",
        ),
        detected_at=NOW - timedelta(hours=5),
    )
    _start_progress(store, active.case_id, started_at=NOW - timedelta(hours=2))

    resolved = store.upsert_detection(
        _detection(
            case_type="fulfillment_backlog",
            dedupe_suffix="fulfillment_backlog/business/orders/commerce.fulfillment/daily",
            severity="warning",
            run_id="run-resolved",
        ),
        detected_at=NOW - timedelta(days=1),
    )
    _start_progress(store, resolved.case_id, started_at=NOW - timedelta(hours=20))
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved fixture",
        transitioned_at=NOW - timedelta(hours=1),
    )

    result = list_recently_in_progress_cases(store, business_id="artemea")

    assert result["in_progress_total"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == active.case_id


def test_is_scoped_per_business_and_respects_limit():
    store = InMemoryOperationalCaseStore()
    mine_old = store.upsert_detection(_detection(run_id="run-mine-old"), detected_at=NOW - timedelta(days=2))
    _start_progress(store, mine_old.case_id, started_at=NOW - timedelta(days=1))
    mine_new = store.upsert_detection(
        _detection(
            dedupe_suffix="stockout_risk/product/new/commerce.inventory/daily",
            run_id="run-mine-new",
        ),
        detected_at=NOW - timedelta(hours=4),
    )
    _start_progress(store, mine_new.case_id, started_at=NOW - timedelta(hours=2))
    other = store.upsert_detection(
        _detection(business_id="other-shop", run_id="run-other"),
        detected_at=NOW - timedelta(hours=6),
    )
    _start_progress(store, other.case_id, started_at=NOW - timedelta(minutes=10))

    result = list_recently_in_progress_cases(store, business_id="artemea", limit="1")

    assert result["in_progress_total"] == 2
    assert result["limit"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == mine_new.case_id


def test_rejects_invalid_limit():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        list_recently_in_progress_cases(store, business_id="artemea", limit="not-an-int")

    assert exc_info.value.code == "invalid_limit"
    assert exc_info.value.status_code == 400

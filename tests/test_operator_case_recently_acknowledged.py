"""Tests for the deterministic recently-acknowledged cases projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
)
from app.brain.operator_api import (
    OperatorAPIError,
    list_recently_acknowledged_cases,
)


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-ack-1",
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


def _acknowledge(
    store: InMemoryOperationalCaseStore,
    case_id: str,
    *,
    acknowledged_at: datetime,
) -> None:
    store.transition_case(
        case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=acknowledged_at,
    )


def test_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = list_recently_acknowledged_cases(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "acknowledged_total": 0,
        "cases": [],
        "limit": 50,
        "count": 0,
    }


def test_orders_most_recently_acknowledged_first():
    store = InMemoryOperationalCaseStore()

    schedule = [
        ("a", "stockout_risk", "stockout_risk/business/monitored/commerce.inventory/daily", "critical", timedelta(days=4)),
        ("b", "sales_drop", "sales_drop/channel/all/commerce.revenue/daily", "warning", timedelta(days=1)),
        ("c", "sales_drop", "sales_drop/channel/meta_ads/commerce.revenue/daily", "warning", timedelta(hours=10)),
        ("d", "unanswered_conversations", "unanswered_conversations/channel/whatsapp/support.conversations/daily", "warning", timedelta(hours=2)),
    ]
    cases_by_run: dict[str, str] = {}
    for run_id, case_type, dedupe_suffix, severity, since_ack in schedule:
        opened_at = NOW - since_ack - timedelta(hours=6)
        ack_at = NOW - since_ack
        case = store.upsert_detection(
            _detection(
                case_type=case_type,
                dedupe_suffix=dedupe_suffix,
                severity=severity,
                priority=70,
                run_id=f"run-{run_id}",
            ),
            detected_at=opened_at,
        )
        _acknowledge(store, case.case_id, acknowledged_at=ack_at)
        cases_by_run[run_id] = case.case_id

    result = list_recently_acknowledged_cases(store, business_id="artemea")

    assert result["acknowledged_total"] == 4
    assert result["count"] == 4
    returned_ids = [entry["case_id"] for entry in result["cases"]]
    assert returned_ids == [
        cases_by_run["d"],
        cases_by_run["c"],
        cases_by_run["b"],
        cases_by_run["a"],
    ]
    first = result["cases"][0]
    assert first["status"] == "acknowledged"
    assert first["case_type"] == "unanswered_conversations"
    assert first["acknowledged_at"].startswith("2026-05-26T10:00:00")
    assert first["acknowledgment_seconds"] == int(timedelta(hours=6).total_seconds())


def test_respects_limit():
    store = InMemoryOperationalCaseStore()

    schedule = [
        ("first", timedelta(days=3)),
        ("second", timedelta(days=2)),
        ("third", timedelta(days=1)),
    ]
    cases_by_run: dict[str, str] = {}
    for index, (run_id, since_ack) in enumerate(schedule):
        opened_at = NOW - since_ack - timedelta(hours=4)
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/c{index}/commerce.revenue/daily",
                severity="warning",
                run_id=f"run-{run_id}",
            ),
            detected_at=opened_at,
        )
        _acknowledge(store, case.case_id, acknowledged_at=NOW - since_ack)
        cases_by_run[run_id] = case.case_id

    result = list_recently_acknowledged_cases(store, business_id="artemea", limit="2")

    assert result["limit"] == 2
    assert result["acknowledged_total"] == 3
    assert result["count"] == 2
    assert [entry["case_id"] for entry in result["cases"]] == [
        cases_by_run["third"],
        cases_by_run["second"],
    ]


def test_excludes_open_and_resolved_cases():
    store = InMemoryOperationalCaseStore()

    # Open (not yet acknowledged) — should be excluded.
    store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-open"),
        detected_at=NOW - timedelta(hours=2),
    )

    # Acknowledged — included.
    ack_only = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            severity="warning",
            run_id="run-ack",
        ),
        detected_at=NOW - timedelta(hours=4),
    )
    _acknowledge(store, ack_only.case_id, acknowledged_at=NOW - timedelta(hours=3))

    # Resolved (passed through acknowledged) — excluded, recently_resolved owns it.
    resolved = store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/support.conversations/daily",
            severity="warning",
            run_id="run-resolved",
        ),
        detected_at=NOW - timedelta(days=1),
    )
    _acknowledge(store, resolved.case_id, acknowledged_at=NOW - timedelta(hours=22))
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=NOW - timedelta(hours=2),
    )

    result = list_recently_acknowledged_cases(store, business_id="artemea")

    assert result["acknowledged_total"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == ack_only.case_id
    assert result["cases"][0]["status"] == "acknowledged"


def test_is_scoped_per_business():
    store = InMemoryOperationalCaseStore()
    mine = store.upsert_detection(
        _detection(business_id="artemea", run_id="run-mine"),
        detected_at=NOW - timedelta(days=1),
    )
    _acknowledge(store, mine.case_id, acknowledged_at=NOW - timedelta(hours=4))
    other = store.upsert_detection(
        _detection(business_id="other-shop", run_id="run-other"),
        detected_at=NOW - timedelta(days=2),
    )
    _acknowledge(store, other.case_id, acknowledged_at=NOW - timedelta(hours=1))

    result = list_recently_acknowledged_cases(store, business_id="artemea")

    assert result["acknowledged_total"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == mine.case_id


def test_tiebreaks_on_case_id():
    store = InMemoryOperationalCaseStore()
    opened_at = NOW - timedelta(days=2)
    ack_at = NOW - timedelta(hours=6)
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
        _acknowledge(store, case.case_id, acknowledged_at=ack_at)
        case_ids.append(case.case_id)

    result = list_recently_acknowledged_cases(store, business_id="artemea")

    assert result["acknowledged_total"] == 3
    returned_ids = [entry["case_id"] for entry in result["cases"]]
    assert returned_ids == sorted(case_ids)
    assert all(entry["acknowledged_at"] == ack_at.isoformat() for entry in result["cases"])


def test_rejects_invalid_limit():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        list_recently_acknowledged_cases(
            store, business_id="artemea", limit="not-an-int"
        )

    assert exc_info.value.code == "invalid_limit"
    assert exc_info.value.status_code == 400

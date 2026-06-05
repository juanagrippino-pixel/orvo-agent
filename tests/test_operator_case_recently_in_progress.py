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

NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


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
        title="Caso en progreso",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def _mark_in_progress(
    store: InMemoryOperationalCaseStore,
    case_id: str,
    *,
    progressed_at: datetime,
) -> None:
    store.transition_case(
        case_id,
        status="in_progress",
        actor_type="operator",
        actor_ref="operator@example.com",
        transitioned_at=progressed_at,
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

    result = list_recently_in_progress_cases(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "in_progress_total": 0,
        "cases": [],
        "limit": 50,
        "count": 0,
    }


def test_orders_most_recently_marked_in_progress_first_from_timeline():
    store = InMemoryOperationalCaseStore()
    cases_by_run: dict[str, str] = {}
    for index, (run_id, progressed_at) in enumerate(
        (
            ("older", NOW - timedelta(hours=6)),
            ("newest", NOW - timedelta(hours=1)),
            ("middle", NOW - timedelta(hours=3)),
        )
    ):
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/{index}/commerce.revenue/daily",
                severity="warning",
                run_id=f"run-{run_id}",
            ),
            detected_at=NOW - timedelta(days=1),
        )
        _mark_in_progress(store, case.case_id, progressed_at=progressed_at)
        cases_by_run[run_id] = case.case_id

    result = list_recently_in_progress_cases(store, business_id="artemea")

    assert result["in_progress_total"] == 3
    assert result["count"] == 3
    assert [entry["case_id"] for entry in result["cases"]] == [
        cases_by_run["newest"],
        cases_by_run["middle"],
        cases_by_run["older"],
    ]
    first = result["cases"][0]
    assert first["status"] == "in_progress"
    assert first["in_progress_at"] == (NOW - timedelta(hours=1)).isoformat()
    assert first["handling_seconds"] == 23 * 60 * 60


def test_excludes_open_acknowledged_and_resolved_cases():
    store = InMemoryOperationalCaseStore()
    in_progress = store.upsert_detection(
        _detection(case_type="stockout_risk", run_id="run-in-progress"),
        detected_at=NOW - timedelta(hours=5),
    )
    _mark_in_progress(store, in_progress.case_id, progressed_at=NOW - timedelta(hours=2))

    open_case = store.upsert_detection(
        _detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/open/commerce.revenue/daily",
            severity="warning",
            run_id="run-open",
        ),
        detected_at=NOW - timedelta(hours=1),
    )
    acknowledged = store.upsert_detection(
        _detection(
            case_type="unanswered_conversations",
            dedupe_suffix="unanswered_conversations/channel/whatsapp/support.conversations/daily",
            severity="warning",
            run_id="run-ack",
        ),
        detected_at=NOW - timedelta(hours=4),
    )
    _acknowledge(store, acknowledged.case_id, acknowledged_at=NOW - timedelta(hours=3))
    resolved = store.upsert_detection(
        _detection(
            case_type="data_stale",
            dedupe_suffix="data_stale/source/tiendanube/runtime.freshness/daily",
            severity="warning",
            run_id="run-resolved",
        ),
        detected_at=NOW - timedelta(hours=8),
    )
    _mark_in_progress(store, resolved.case_id, progressed_at=NOW - timedelta(hours=7))
    store.transition_case(
        resolved.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Resolved in test fixture",
        transitioned_at=NOW - timedelta(hours=6),
    )

    result = list_recently_in_progress_cases(store, business_id="artemea")

    assert result["in_progress_total"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == in_progress.case_id
    returned_case_ids = {entry["case_id"] for entry in result["cases"]}
    assert open_case.case_id not in returned_case_ids
    assert acknowledged.case_id not in returned_case_ids
    assert resolved.case_id not in returned_case_ids


def test_respects_limit_and_business_scope():
    store = InMemoryOperationalCaseStore()
    first = store.upsert_detection(
        _detection(run_id="run-first"),
        detected_at=NOW - timedelta(days=1),
    )
    _mark_in_progress(store, first.case_id, progressed_at=NOW - timedelta(hours=4))
    second = store.upsert_detection(
        _detection(
            dedupe_suffix="stockout_risk/business/second/commerce.inventory/daily",
            run_id="run-second",
        ),
        detected_at=NOW - timedelta(days=1),
    )
    _mark_in_progress(store, second.case_id, progressed_at=NOW - timedelta(hours=1))
    other = store.upsert_detection(
        _detection(business_id="other-shop", run_id="run-other"),
        detected_at=NOW - timedelta(days=1),
    )
    _mark_in_progress(store, other.case_id, progressed_at=NOW)

    result = list_recently_in_progress_cases(store, business_id="artemea", limit="1")

    assert result["limit"] == 1
    assert result["in_progress_total"] == 2
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == second.case_id


def test_tiebreaks_on_case_id():
    store = InMemoryOperationalCaseStore()
    progressed_at = NOW - timedelta(hours=2)
    case_ids: list[str] = []
    for suffix in ("alpha", "beta", "gamma"):
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/{suffix}/commerce.revenue/daily",
                severity="warning",
                run_id=f"run-{suffix}",
            ),
            detected_at=NOW - timedelta(days=1),
        )
        _mark_in_progress(store, case.case_id, progressed_at=progressed_at)
        case_ids.append(case.case_id)

    result = list_recently_in_progress_cases(store, business_id="artemea")

    assert result["in_progress_total"] == 3
    assert [entry["case_id"] for entry in result["cases"]] == sorted(case_ids)
    assert all(entry["in_progress_at"] == progressed_at.isoformat() for entry in result["cases"])


def test_rejects_invalid_limit():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        list_recently_in_progress_cases(store, business_id="artemea", limit="not-an-int")

    assert exc_info.value.code == "invalid_limit"
    assert exc_info.value.status_code == 400

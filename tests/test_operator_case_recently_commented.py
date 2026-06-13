"""Tests for the deterministic recently-commented cases projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import InMemoryOperationalCaseStore, OperationalCaseDetection
from app.brain.operator_api import OperatorAPIError, list_recently_commented_cases


NOW = datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


def _detection(
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-commented-1",
) -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Caso access_token=raw_title_secret",
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado access_token=raw_entity_secret"},
        evidence_refs=[f"evidence://{business_id}/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def _comment(
    store: InMemoryOperationalCaseStore,
    case_id: str,
    *,
    comment: str,
    commented_at: datetime,
    actor_ref: str = "operator@example.com",
) -> None:
    store.add_comment(
        case_id,
        actor_type="operator",
        actor_ref=actor_ref,
        comment=comment,
        commented_at=commented_at,
    )


def test_returns_empty_when_no_cases():
    store = InMemoryOperationalCaseStore()

    result = list_recently_commented_cases(store, business_id="artemea")

    assert result == {
        "business_id": "artemea",
        "projection_type": "recent_case_activity",
        "activity_type": "commented",
        "total": 0,
        "commented_total": 0,
        "cases": [],
        "limit": 50,
        "count": 0,
    }


def test_orders_by_latest_operator_comment_and_redacts_comment_actor_and_title():
    store = InMemoryOperationalCaseStore()
    cases_by_label: dict[str, str] = {}
    for label, commented_delta in (
        ("oldest", timedelta(days=2)),
        ("newer", timedelta(hours=3)),
        ("newest", timedelta(minutes=30)),
    ):
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/{label}/commerce.revenue/daily",
                severity="warning",
                priority=70,
                run_id=f"run-{label}",
            ),
            detected_at=NOW - timedelta(days=3),
        )
        _comment(
            store,
            case.case_id,
            comment=f"follow-up access_token=raw_{label}_comment_secret",
            actor_ref=f"operator access_token=raw_{label}_actor_secret",
            commented_at=NOW - commented_delta,
        )
        cases_by_label[label] = case.case_id

    result = list_recently_commented_cases(store, business_id="artemea")

    assert result["commented_total"] == 3
    assert result["count"] == 3
    assert [entry["case_id"] for entry in result["cases"]] == [
        cases_by_label["newest"],
        cases_by_label["newer"],
        cases_by_label["oldest"],
    ]
    first = result["cases"][0]
    assert first["status"] == "open"
    assert first["case_type"] == "sales_drop"
    assert first["title"] == "Caso access_token=[REDACTED]"
    assert first["entity_scope"] == {
        "kind": "business",
        "id": "monitored",
        "label": "Monitoreado access_token=[REDACTED]",
    }
    assert first["latest_comment_at"].startswith("2026-05-26T11:30:00")
    assert first["latest_comment_summary"] == "follow-up access_token=[REDACTED]"
    assert first["latest_comment_actor_ref"] == "operator access_token=[REDACTED]"
    assert first["comment_count"] == 1
    serialized = str(result)
    assert "raw_newest_comment_secret" not in serialized
    assert "raw_newest_actor_secret" not in serialized
    assert "raw_title_secret" not in serialized
    assert "raw_entity_secret" not in serialized


def test_uses_latest_comment_per_case_respects_limit_and_scopes_business():
    store = InMemoryOperationalCaseStore()
    included_older = store.upsert_detection(
        _detection(run_id="run-included-older", dedupe_suffix="commented/included-older"),
        detected_at=NOW - timedelta(days=3),
    )
    _comment(
        store,
        included_older.case_id,
        comment="older first",
        commented_at=NOW - timedelta(hours=6),
    )
    _comment(
        store,
        included_older.case_id,
        comment="older latest",
        commented_at=NOW - timedelta(hours=4),
    )
    included_newer = store.upsert_detection(
        _detection(run_id="run-included-newer", dedupe_suffix="commented/included-newer"),
        detected_at=NOW - timedelta(days=2),
    )
    _comment(
        store,
        included_newer.case_id,
        comment="newer latest",
        commented_at=NOW - timedelta(hours=1),
    )
    no_comment = store.upsert_detection(
        _detection(run_id="run-no-comment", dedupe_suffix="commented/no-comment"),
        detected_at=NOW - timedelta(minutes=5),
    )
    other_business = store.upsert_detection(
        _detection(
            business_id="other-shop",
            run_id="run-other",
            dedupe_suffix="commented/other",
        ),
        detected_at=NOW - timedelta(hours=2),
    )
    _comment(
        store,
        other_business.case_id,
        comment="other business latest",
        commented_at=NOW - timedelta(minutes=2),
    )

    result = list_recently_commented_cases(store, business_id="artemea", limit="1")

    assert result["commented_total"] == 2
    assert result["limit"] == 1
    assert result["count"] == 1
    assert result["cases"][0]["case_id"] == included_newer.case_id
    assert result["cases"][0]["latest_comment_summary"] == "newer latest"
    assert result["cases"][0]["comment_count"] == 1
    returned_case_ids = {entry["case_id"] for entry in result["cases"]}
    assert included_older.case_id not in returned_case_ids
    assert no_comment.case_id not in returned_case_ids
    assert other_business.case_id not in returned_case_ids


def test_tiebreaks_on_case_id():
    store = InMemoryOperationalCaseStore()
    case_ids: list[str] = []
    for suffix in ("alpha", "beta", "gamma"):
        case = store.upsert_detection(
            _detection(
                case_type="sales_drop",
                dedupe_suffix=f"sales_drop/channel/{suffix}/commerce.revenue/daily",
                severity="warning",
                run_id=f"run-{suffix}",
            ),
            detected_at=NOW - timedelta(days=2),
        )
        _comment(store, case.case_id, comment=f"comment {suffix}", commented_at=NOW)
        case_ids.append(case.case_id)

    result = list_recently_commented_cases(store, business_id="artemea")

    assert result["commented_total"] == 3
    assert [entry["case_id"] for entry in result["cases"]] == sorted(case_ids)
    assert all(entry["latest_comment_at"] == NOW.isoformat() for entry in result["cases"])


def test_rejects_invalid_limit():
    store = InMemoryOperationalCaseStore()

    with pytest.raises(OperatorAPIError) as exc_info:
        list_recently_commented_cases(store, business_id="artemea", limit="not-an-int")

    assert exc_info.value.code == "invalid_limit"
    assert exc_info.value.status_code == 400

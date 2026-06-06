"""HTTP endpoint tests for the recently-updated case activity endpoint."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import OperationalCaseDetection, OperationalCaseSeverity, OperationalCaseType
from app.brain.storage import SQLiteOperationalCaseStore, init_schema

AUTH_WITH_SCOPE = {
    "Authorization": "Bearer test-internal-token",
    "X-Orvo-Operator": "operator@example.com",
    "X-Orvo-Businesses": "artemea",
}
AUTH_WRONG_SCOPE = {
    "Authorization": "Bearer test-internal-token",
    "X-Orvo-Operator": "operator@example.com",
    "X-Orvo-Businesses": "other-biz",
}


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test_brain.sqlite3"
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    with closing(sqlite3.connect(str(db_path))) as conn:
        init_schema(conn)
    yield db_path


def _detection(
    *,
    business_id: str = "artemea",
    case_type: OperationalCaseType = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: OperationalCaseSeverity = "critical",
    priority: int = 100,
    run_id: str = "run-1",
) -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Recently updated case under test access_token=raw_title_secret",
        severity=severity,
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored"},
        evidence_refs=[f"evidence://{business_id}/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
    )


def _seed_open_case(
    db_path,
    *,
    business_id: str = "artemea",
    case_type: OperationalCaseType = "stockout_risk",
    opened_hours_ago: int = 2,
    run_id: str = "run-1",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
) -> str:
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    case = store.upsert_detection(
        _detection(
            business_id=business_id,
            case_type=case_type,
            run_id=run_id,
            dedupe_suffix=dedupe_suffix,
        ),
        detected_at=now - timedelta(hours=opened_hours_ago),
    )
    conn.close()
    return case.case_id


def _comment_case(
    db_path,
    case_id: str,
    *,
    commented_minutes_ago: int,
    comment: str = "comment",
    actor_ref: str = "operator:juan",
) -> None:
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    store.add_comment(
        case_id,
        actor_type="operator",
        actor_ref=actor_ref,
        comment=comment,
        commented_at=datetime.now(timezone.utc) - timedelta(minutes=commented_minutes_ago),
    )
    conn.close()


def _resolve_case(db_path, case_id: str, *, resolved_minutes_ago: int) -> None:
    resolved_at = datetime.now(timezone.utc) - timedelta(minutes=resolved_minutes_ago)
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    store.transition_case(
        case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=resolved_at - timedelta(minutes=2),
    )
    store.transition_case(
        case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator access_token=raw_actor_secret",
        reason="resolved access_token=raw_reason_secret",
        transitioned_at=resolved_at,
    )
    conn.close()


def test_recently_updated_returns_scoped_cases_ordered_by_latest_timeline_event_and_redacted(_isolate_db):
    from server import app

    older = _seed_open_case(
        _isolate_db,
        opened_hours_ago=8,
        run_id="run-older",
        dedupe_suffix="recent/updated/older",
    )
    newest = _seed_open_case(
        _isolate_db,
        opened_hours_ago=8,
        run_id="run-newest",
        dedupe_suffix="recent/updated/newest",
    )
    opened_only = _seed_open_case(
        _isolate_db,
        opened_hours_ago=1,
        run_id="run-opened-only",
        dedupe_suffix="recent/updated/opened-only",
    )
    other_business = _seed_open_case(
        _isolate_db,
        business_id="other-biz",
        opened_hours_ago=8,
        run_id="run-other",
        dedupe_suffix="recent/updated/other",
    )

    _comment_case(_isolate_db, older, commented_minutes_ago=30, comment="older comment")
    _resolve_case(_isolate_db, newest, resolved_minutes_ago=5)
    _comment_case(_isolate_db, other_business, commented_minutes_ago=1, comment="other business")

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/recently-updated?limit=2",
        headers=AUTH_WITH_SCOPE,
    )

    assert response.status_code == 200
    response_text = response.get_data(as_text=True)
    assert "raw_actor_secret" not in response_text
    assert "raw_reason_secret" not in response_text
    assert "raw_title_secret" not in response_text
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["updated_total"] == 3
    assert data["limit"] == 2
    assert data["count"] == 2
    assert data["cases"][0]["case_id"] == newest
    assert data["cases"][0]["status"] == "resolved"
    assert data["cases"][0]["title"] == "Recently updated case under test access_token=[REDACTED]"
    assert data["cases"][0]["latest_activity_type"] == "status_changed"
    assert data["cases"][0]["latest_activity_summary"] == "resolved access_token=[REDACTED]"
    assert data["cases"][0]["latest_activity_actor_ref"] == "operator access_token=[REDACTED]"
    returned_case_ids = {case["case_id"] for case in data["cases"]}
    assert older in returned_case_ids
    assert opened_only not in returned_case_ids
    assert other_business not in returned_case_ids


def test_recently_updated_requires_internal_auth(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/recently-updated",
    )

    assert response.status_code == 401
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "unauthorized"
    assert body["redaction_applied"] is True


def test_recently_updated_enforces_explicit_business_scope(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/recently-updated",
        headers=AUTH_WRONG_SCOPE,
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "forbidden"
    assert body["redaction_applied"] is True

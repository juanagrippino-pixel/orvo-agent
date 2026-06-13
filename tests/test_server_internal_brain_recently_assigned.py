"""HTTP endpoint tests for the recently-assigned case listing endpoint."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import (
    OperationalCaseDetection,
    OperationalCaseSeverity,
    OperationalCaseType,
)
from app.brain.storage import SQLiteOperationalCaseStore, init_schema

AUTH = {"Authorization": "Bearer test-internal-token"}
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
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Recently assigned case under test access_token=raw_title_secret",
        severity=severity,
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored"},
        evidence_refs=[evidence_ref],
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


def _assign_case(
    db_path,
    case_id: str,
    *,
    assigned_minutes_ago: int,
    assignee_ref: str = "owner@example.com",
) -> None:
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    store.assign_case(
        case_id,
        actor_type="operator",
        actor_ref="operator:juan",
        assignee_ref=assignee_ref,
        assigned_at=datetime.now(timezone.utc) - timedelta(minutes=assigned_minutes_ago),
    )
    conn.close()


def _resolve_case(db_path, case_id: str, *, resolved_minutes_ago: int) -> None:
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    store.transition_case(
        case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=datetime.now(timezone.utc) - timedelta(minutes=resolved_minutes_ago + 1),
    )
    store.transition_case(
        case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator:juan",
        reason="done",
        transitioned_at=datetime.now(timezone.utc) - timedelta(minutes=resolved_minutes_ago),
    )
    conn.close()


def test_recently_assigned_returns_scoped_in_flight_cases_ordered_newest_first_and_redacted(_isolate_db):
    from server import app

    older = _seed_open_case(
        _isolate_db,
        opened_hours_ago=8,
        run_id="run-older",
        dedupe_suffix="recent/assigned/older",
    )
    newest = _seed_open_case(
        _isolate_db,
        opened_hours_ago=8,
        run_id="run-newest",
        dedupe_suffix="recent/assigned/newest",
    )
    unassigned = _seed_open_case(
        _isolate_db,
        opened_hours_ago=1,
        run_id="run-unassigned",
        dedupe_suffix="recent/assigned/unassigned",
    )
    other_business = _seed_open_case(
        _isolate_db,
        business_id="other-biz",
        opened_hours_ago=8,
        run_id="run-other",
        dedupe_suffix="recent/assigned/other",
    )
    resolved = _seed_open_case(
        _isolate_db,
        opened_hours_ago=8,
        run_id="run-resolved",
        dedupe_suffix="recent/assigned/resolved",
    )

    _assign_case(_isolate_db, older, assigned_minutes_ago=30)
    _assign_case(
        _isolate_db,
        newest,
        assigned_minutes_ago=5,
        assignee_ref="owner access_token=raw_assignee_secret",
    )
    _assign_case(_isolate_db, other_business, assigned_minutes_ago=1)
    _assign_case(_isolate_db, resolved, assigned_minutes_ago=2)
    _resolve_case(_isolate_db, resolved, resolved_minutes_ago=1)

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/recently-assigned?limit=1",
        headers=AUTH_WITH_SCOPE,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["projection_type"] == "recent_case_activity"
    assert data["activity_type"] == "assigned"
    assert data["total"] == 2
    assert data["assigned_total"] == 2
    assert data["limit"] == 1
    assert data["count"] == 1
    assert data["cases"][0]["case_id"] == newest
    assert data["cases"][0]["status"] == "open"
    assert data["cases"][0]["assignee_ref"] == "owner access_token=[REDACTED]"
    assert data["cases"][0]["assignment_seconds"] >= 0
    serialized = str(body)
    assert "raw_assignee_secret" not in serialized
    assert "raw_title_secret" not in serialized
    returned_case_ids = {case["case_id"] for case in data["cases"]}
    assert older not in returned_case_ids
    assert unassigned not in returned_case_ids
    assert other_business not in returned_case_ids
    assert resolved not in returned_case_ids


def test_recently_assigned_requires_internal_auth(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/recently-assigned",
    )

    assert response.status_code == 401
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "unauthorized"
    assert body["redaction_applied"] is True


def test_recently_assigned_enforces_explicit_business_scope(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/recently-assigned",
        headers=AUTH_WRONG_SCOPE,
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "forbidden"
    assert body["redaction_applied"] is True

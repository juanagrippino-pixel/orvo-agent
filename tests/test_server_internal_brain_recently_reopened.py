"""HTTP endpoint tests for the recently-reopened case listing endpoint."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import OperationalCaseDetection, OperationalCaseSeverity, OperationalCaseType
from app.brain.storage import SQLiteOperationalCaseStore, init_schema

AUTH = {"Authorization": "Bearer test-internal-token"}


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
        title="Reopened case api_key=raw_reopened_title_secret",
        severity=severity,
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored"},
        evidence_refs=[evidence_ref],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report?access_token=raw_reopened_artifact_secret"],
    )


def _seed_open_case(
    db_path,
    *,
    business_id: str = "artemea",
    case_type: OperationalCaseType = "stockout_risk",
    opened_hours_ago: int = 72,
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


def _resolve_case(db_path, case_id: str, *, resolved_minutes_ago: int) -> None:
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    store.transition_case(
        case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=datetime.now(timezone.utc) - timedelta(minutes=resolved_minutes_ago + 10),
    )
    store.transition_case(
        case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator:juan",
        reason="done access_token=raw_reopened_reason_secret",
        transitioned_at=datetime.now(timezone.utc) - timedelta(minutes=resolved_minutes_ago),
    )
    conn.close()


def _reopen_case(
    db_path,
    *,
    business_id: str = "artemea",
    run_id: str,
    dedupe_suffix: str,
    reopened_minutes_ago: int,
) -> str:
    case_id = _seed_open_case(
        db_path,
        business_id=business_id,
        run_id=f"original-{run_id}",
        dedupe_suffix=dedupe_suffix,
    )
    _resolve_case(db_path, case_id, resolved_minutes_ago=reopened_minutes_ago + 10)
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    reopened = store.upsert_detection(
        _detection(
            business_id=business_id,
            run_id=run_id,
            dedupe_suffix=dedupe_suffix,
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(minutes=reopened_minutes_ago),
    )
    conn.close()
    return reopened.case_id


def test_recently_reopened_returns_scoped_actionable_cases_ordered_newest_first(_isolate_db):
    from server import app

    older = _reopen_case(
        _isolate_db,
        run_id="run-older",
        dedupe_suffix="recent/reopened/older",
        reopened_minutes_ago=30,
    )
    newest = _reopen_case(
        _isolate_db,
        run_id="run-newest",
        dedupe_suffix="recent/reopened/newest",
        reopened_minutes_ago=5,
    )
    other_business = _reopen_case(
        _isolate_db,
        business_id="other-biz",
        run_id="run-other",
        dedupe_suffix="recent/reopened/other",
        reopened_minutes_ago=1,
    )
    never_reopened = _seed_open_case(
        _isolate_db,
        run_id="run-open",
        dedupe_suffix="recent/reopened/open",
        opened_hours_ago=1,
    )
    terminal_again = _reopen_case(
        _isolate_db,
        run_id="run-terminal",
        dedupe_suffix="recent/reopened/terminal",
        reopened_minutes_ago=3,
    )
    _resolve_case(_isolate_db, terminal_again, resolved_minutes_ago=1)

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/recently-reopened?limit=1",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    assert "raw_reopened" not in str(body)
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["reopened_total"] == 2
    assert data["limit"] == 1
    assert data["count"] == 1
    assert data["cases"][0]["case_id"] == newest
    assert data["cases"][0]["status"] == "open"
    assert data["cases"][0]["time_to_reopen_seconds"] >= 0
    returned_case_ids = {case["case_id"] for case in data["cases"]}
    assert older not in returned_case_ids
    assert other_business not in returned_case_ids
    assert never_reopened not in returned_case_ids
    assert terminal_again not in returned_case_ids


def test_recently_reopened_requires_internal_auth(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/recently-reopened",
    )

    assert response.status_code == 401
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "unauthorized"
    assert body["redaction_applied"] is True

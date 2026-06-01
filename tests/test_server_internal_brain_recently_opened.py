"""HTTP endpoint tests for the recently-opened case listing endpoint."""

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
        title="Recently opened case under test",
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


def _acknowledge_case(db_path, case_id: str) -> None:
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    store.transition_case(
        case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=datetime.now(timezone.utc),
    )
    conn.close()


def test_recently_opened_returns_scoped_open_cases_ordered_newest_first(_isolate_db):
    from server import app

    older = _seed_open_case(
        _isolate_db,
        opened_hours_ago=8,
        run_id="run-older",
        dedupe_suffix="recent/open/older",
    )
    newest = _seed_open_case(
        _isolate_db,
        opened_hours_ago=1,
        run_id="run-newest",
        dedupe_suffix="recent/open/newest",
    )
    acknowledged = _seed_open_case(
        _isolate_db,
        opened_hours_ago=0,
        run_id="run-acknowledged",
        dedupe_suffix="recent/open/acknowledged",
    )
    _acknowledge_case(_isolate_db, acknowledged)
    _seed_open_case(
        _isolate_db,
        business_id="other-biz",
        opened_hours_ago=0,
        run_id="run-other",
        dedupe_suffix="recent/open/other",
    )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/recently-opened?limit=1",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["open_total"] == 2
    assert data["limit"] == 1
    assert data["count"] == 1
    assert data["cases"][0]["case_id"] == newest
    assert data["cases"][0]["status"] == "open"
    returned_case_ids = {case["case_id"] for case in data["cases"]}
    assert older not in returned_case_ids
    assert acknowledged not in returned_case_ids

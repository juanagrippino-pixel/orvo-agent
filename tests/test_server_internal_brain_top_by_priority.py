"""HTTP endpoint tests for the top-by-priority case listing endpoint."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from app.brain.operational_cases import OperationalCaseDetection
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
    case_type: str = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    severity: str = "critical",
    priority: int = 100,
    run_id: str = "run-1",
) -> OperationalCaseDetection:
    evidence_ref = f"evidence://{business_id}/{run_id}/{case_type}"
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title="Case under test",
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
    case_type: str = "stockout_risk",
    priority: int = 100,
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
            priority=priority,
            run_id=run_id,
            dedupe_suffix=dedupe_suffix,
        ),
        detected_at=now - timedelta(hours=opened_hours_ago),
    )
    conn.close()
    return case.case_id


def test_top_by_priority_returns_empty_when_no_cases(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/top-by-priority",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["actionable_total"] == 0
    assert data["cases"] == []
    assert data["count"] == 0


def test_top_by_priority_orders_by_priority_desc(_isolate_db):
    from server import app

    _seed_open_case(_isolate_db, priority=20, run_id="run-low", dedupe_suffix="low/1")
    _seed_open_case(_isolate_db, priority=95, run_id="run-high", dedupe_suffix="high/1")
    _seed_open_case(_isolate_db, priority=60, run_id="run-mid", dedupe_suffix="mid/1")

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/top-by-priority",
        headers=AUTH,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["actionable_total"] == 3
    priorities = [c["priority_score"] for c in data["cases"]]
    assert priorities == [95, 60, 20]


def test_top_by_priority_respects_limit_param(_isolate_db):
    from server import app

    for i in range(5):
        _seed_open_case(
            _isolate_db,
            priority=50 + i,
            run_id=f"run-{i}",
            dedupe_suffix=f"case/{i}",
        )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/top-by-priority?limit=2",
        headers=AUTH,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["actionable_total"] == 5
    assert data["count"] == 2
    assert data["limit"] == 2
    # Highest priority should be first (54, then 53)
    priorities = [c["priority_score"] for c in data["cases"]]
    assert priorities == [54, 53]


def test_top_by_priority_scopes_to_business_id(_isolate_db):
    from server import app

    _seed_open_case(_isolate_db, business_id="artemea", priority=80)

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/other-biz/cases/top-by-priority",
        headers=AUTH,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["business_id"] == "other-biz"
    assert data["actionable_total"] == 0
    assert data["cases"] == []


def test_top_by_priority_rejects_unauthorized(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/top-by-priority",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


def test_top_by_priority_returns_503_when_auth_not_configured(_isolate_db, monkeypatch):
    from server import app

    monkeypatch.delenv("ORVO_INTERNAL_OPERATOR_TOKEN", raising=False)

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/top-by-priority",
        headers=AUTH,
    )

    assert response.status_code == 503
    body = response.get_json()
    assert body["error"]["code"] == "internal_auth_not_configured"


def test_top_by_priority_includes_age_seconds_for_context(_isolate_db):
    from server import app

    _seed_open_case(_isolate_db, priority=85, opened_hours_ago=4)

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/top-by-priority",
        headers=AUTH,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["count"] == 1
    case_item = data["cases"][0]
    assert case_item["priority_score"] == 85
    assert case_item["age_seconds"] >= 14400  # >= 4 hours
    assert "case_id" in case_item
    assert "case_type" in case_item
    assert "status" in case_item

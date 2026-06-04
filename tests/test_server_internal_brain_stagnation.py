"""HTTP endpoint tests for the case queue stagnation endpoint."""

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
    opened_hours_ago: int = 2,
    run_id: str = "run-1",
) -> str:
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    case = store.upsert_detection(
        _detection(business_id=business_id, run_id=run_id),
        detected_at=now - timedelta(hours=opened_hours_ago),
    )
    conn.close()
    return case.case_id


def test_case_stagnation_returns_empty_summary_when_no_cases(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/stagnation",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["actionable_total"] == 0
    assert all(count == 0 for count in data["by_idle_bucket"].values())
    assert data["most_stalled_actionable"] is None


def test_case_stagnation_returns_idle_buckets_for_actionable_cases(_isolate_db):
    from server import app

    _seed_open_case(_isolate_db, opened_hours_ago=3)

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/stagnation",
        headers=AUTH,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["actionable_total"] == 1
    assert data["by_idle_bucket"]["under_6h"] == 1
    assert data["most_stalled_actionable"] is not None
    assert data["most_stalled_actionable"]["idle_seconds"] >= 10800  # >= 3h


def test_case_stagnation_scopes_to_business_id(_isolate_db):
    from server import app

    _seed_open_case(_isolate_db, business_id="artemea")

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/other-biz/cases/stagnation",
        headers=AUTH,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["business_id"] == "other-biz"
    assert data["actionable_total"] == 0


def test_case_stagnation_rejects_unauthorized_request(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/stagnation",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


def test_case_stagnation_returns_503_when_auth_not_configured(_isolate_db, monkeypatch):
    from server import app

    monkeypatch.delenv("ORVO_INTERNAL_OPERATOR_TOKEN", raising=False)

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/cases/stagnation",
        headers=AUTH,
    )

    assert response.status_code == 503
    body = response.get_json()
    assert body["error"]["code"] == "internal_auth_not_configured"

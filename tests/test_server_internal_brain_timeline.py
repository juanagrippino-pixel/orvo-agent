"""HTTP endpoint tests for the case timeline endpoint."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import pytest

from app.brain.operational_cases import OperationalCaseDetection
from app.brain.storage import SQLiteOperationalCaseStore, init_schema


def _utc(hour: int = 8) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


AUTH = {"Authorization": "Bearer test-internal-token"}


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test_brain.sqlite3"
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    with closing(sqlite3.connect(str(db_path))) as conn:
        init_schema(conn)
    yield db_path


def _detection(*, business_id: str = "artemea", run_id: str = "run-timeline-1") -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type="stockout_risk",
        dedupe_key=f"{business_id}/stockout_risk/business/monitored/commerce.inventory/daily",
        title="Stock crítico",
        severity="critical",
        priority_score=100,
        entity_scope={"kind": "business", "id": "monitored"},
        evidence_refs=[f"evidence://{business_id}/{run_id}/stockout_risk"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        metadata={"source": "test"},
    )


def _seed_full_lifecycle(db_path) -> str:
    """Create a case with a full lifecycle: opened, updated, comment, ack, resolved.

    Returns the case_id.
    """
    conn = sqlite3.connect(str(db_path))
    store = SQLiteOperationalCaseStore(conn)
    opened = store.upsert_detection(_detection(run_id="run-1"), detected_at=_utc(8))
    store.upsert_detection(_detection(run_id="run-2"), detected_at=_utc(9))
    store.add_comment(
        opened.case_id,
        actor_type="operator",
        actor_ref="operator@example.com",
        comment="Reviewing supplier",
        commented_at=_utc(10),
    )
    store.transition_case(
        opened.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Picked up",
        transitioned_at=_utc(11),
    )
    store.transition_case(
        opened.case_id,
        status="resolved",
        actor_type="operator",
        actor_ref="operator@example.com",
        reason="Restocked",
        transitioned_at=_utc(12),
    )
    return opened.case_id


def test_case_timeline_returns_full_timeline_with_filters_metadata(_isolate_db):
    from server import app

    client = app.test_client()
    case_id = _seed_full_lifecycle(_isolate_db)

    response = client.get(
        f"/internal/brain/businesses/artemea/cases/{case_id}/timeline",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["business_id"] == "artemea"
    data = body["data"]
    assert data["case_id"] == case_id
    assert data["case_status"] == "resolved"
    assert data["count"] == 5
    assert data["total"] == 5
    assert data["limit"] == 50  # default
    event_types = [e["event_type"] for e in data["events"]]
    assert "case_opened" in event_types
    assert "case_updated" in event_types
    assert "operator_comment" in event_types
    assert event_types.count("status_changed") == 2
    assert data["filters"]["event_type"] is None
    assert data["filters"]["actor_type"] is None


def test_case_timeline_filters_by_event_type(_isolate_db):
    from server import app

    client = app.test_client()
    case_id = _seed_full_lifecycle(_isolate_db)

    response = client.get(
        f"/internal/brain/businesses/artemea/cases/{case_id}/timeline",
        headers=AUTH,
        query_string={"event_type": "status_changed"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["count"] == 2
    assert data["total"] == 2
    assert all(e["event_type"] == "status_changed" for e in data["events"])
    assert data["filters"]["event_type"] == "status_changed"


def test_case_timeline_filters_by_actor_type(_isolate_db):
    from server import app

    client = app.test_client()
    case_id = _seed_full_lifecycle(_isolate_db)

    response = client.get(
        f"/internal/brain/businesses/artemea/cases/{case_id}/timeline",
        headers=AUTH,
        query_string={"actor_type": "operator"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["count"] == 3
    assert data["filters"]["actor_type"] == "operator"
    assert {e["event_type"] for e in data["events"]} == {"operator_comment", "status_changed"}


def test_case_timeline_applies_limit(_isolate_db):
    from server import app

    client = app.test_client()
    case_id = _seed_full_lifecycle(_isolate_db)

    response = client.get(
        f"/internal/brain/businesses/artemea/cases/{case_id}/timeline",
        headers=AUTH,
        query_string={"limit": "2"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["count"] == 2
    assert data["total"] == 5
    assert data["limit"] == 2
    # Most recent 2 events kept in chronological order (status_changed x2)
    assert all(e["event_type"] == "status_changed" for e in data["events"])


def test_case_timeline_returns_404_for_unknown_case(_isolate_db):
    from server import app
    import uuid

    client = app.test_client()
    response = client.get(
        f"/internal/brain/businesses/artemea/cases/{uuid.uuid4()}/timeline",
        headers=AUTH,
    )

    assert response.status_code == 404
    body = response.get_json()
    assert body["error"]["code"] == "case_not_found"


def test_case_timeline_rejects_invalid_event_type(_isolate_db):
    from server import app

    client = app.test_client()
    case_id = _seed_full_lifecycle(_isolate_db)

    response = client.get(
        f"/internal/brain/businesses/artemea/cases/{case_id}/timeline",
        headers=AUTH,
        query_string={"event_type": "bogus_event"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_timeline_event_type"


def test_case_timeline_rejects_unauthorized_request(_isolate_db):
    from server import app

    client = app.test_client()
    case_id = _seed_full_lifecycle(_isolate_db)

    response = client.get(
        f"/internal/brain/businesses/artemea/cases/{case_id}/timeline",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


def test_case_timeline_scopes_to_business_id(_isolate_db):
    from server import app

    client = app.test_client()
    case_id = _seed_full_lifecycle(_isolate_db)  # business_id="artemea"

    response = client.get(
        f"/internal/brain/businesses/other-biz/cases/{case_id}/timeline",
        headers=AUTH,
    )

    assert response.status_code == 404

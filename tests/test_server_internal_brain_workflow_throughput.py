"""HTTP endpoint tests for the case workflow throughput endpoint."""

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


def _seed_case_with_lifecycle(
    db_path,
    *,
    business_id: str = "artemea",
    case_type: str = "stockout_risk",
    opened_hours_ago: int = 24,
    ack_minutes_after_open: int | None = 30,
    resolve_hours_after_open: int | None = None,
    priority: int = 100,
    run_id: str = "run-1",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
) -> str:
    now = datetime.now(timezone.utc)
    opened_at = now - timedelta(hours=opened_hours_ago)
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
        detected_at=opened_at,
    )
    if ack_minutes_after_open is not None:
        store.transition_case(
            case.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="operator://test",
            transitioned_at=opened_at + timedelta(minutes=ack_minutes_after_open),
        )
    if resolve_hours_after_open is not None:
        store.transition_case(
            case.case_id,
            status="resolved",
            actor_type="operator",
            actor_ref="operator://test",
            reason="Resolved in test fixture",
            transitioned_at=opened_at + timedelta(hours=resolve_hours_after_open),
        )
    conn.close()
    return case.case_id


def test_workflow_throughput_returns_empty_when_no_cases(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/workflow/throughput",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["total"] == 0
    assert data["acknowledged_count"] == 0
    assert data["resolved_count"] == 0


def test_workflow_throughput_counts_acknowledged_and_resolved(_isolate_db):
    from server import app

    _seed_case_with_lifecycle(
        _isolate_db,
        ack_minutes_after_open=30,
        resolve_hours_after_open=4,
        dedupe_suffix="case-a",
    )
    _seed_case_with_lifecycle(
        _isolate_db,
        ack_minutes_after_open=60,
        resolve_hours_after_open=None,
        dedupe_suffix="case-b",
    )
    _seed_case_with_lifecycle(
        _isolate_db,
        ack_minutes_after_open=None,
        resolve_hours_after_open=None,
        dedupe_suffix="case-c",
    )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/workflow/throughput",
        headers=AUTH,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total"] == 3
    assert data["acknowledged_count"] == 2
    assert data["resolved_count"] == 1


def test_workflow_throughput_scopes_to_business_id(_isolate_db):
    from server import app

    _seed_case_with_lifecycle(
        _isolate_db,
        business_id="artemea",
        ack_minutes_after_open=30,
    )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/other-biz/workflow/throughput",
        headers=AUTH,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["business_id"] == "other-biz"
    assert data["total"] == 0


def test_workflow_throughput_by_priority_bracket_exposes_split_projection(_isolate_db):
    from server import app

    _seed_case_with_lifecycle(
        _isolate_db,
        priority=95,
        ack_minutes_after_open=30,
        resolve_hours_after_open=4,
        dedupe_suffix="case-high",
    )
    _seed_case_with_lifecycle(
        _isolate_db,
        priority=65,
        ack_minutes_after_open=None,
        resolve_hours_after_open=None,
        dedupe_suffix="case-medium",
    )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/workflow/throughput/by-priority-bracket",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["total"] == 2
    assert data["totals_by_priority_bracket"] == {"high": 1, "medium": 1}
    assert data["acknowledged_by_priority_bracket"] == {"high": 1}
    assert data["resolved_by_priority_bracket"] == {"high": 1}
    assert data["time_to_acknowledge_seconds_by_priority_bracket"]["high"] == {
        "min": 1800,
        "max": 1800,
        "avg": 1800,
        "median": 1800,
    }


def test_workflow_throughput_by_case_type_exposes_split_projection(_isolate_db):
    from server import app

    _seed_case_with_lifecycle(
        _isolate_db,
        case_type="stockout_risk",
        ack_minutes_after_open=30,
        resolve_hours_after_open=4,
        dedupe_suffix="case-stockout",
    )
    _seed_case_with_lifecycle(
        _isolate_db,
        case_type="sales_drop",
        ack_minutes_after_open=60,
        resolve_hours_after_open=None,
        dedupe_suffix="case-sales-drop",
    )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/workflow/throughput/by-case-type",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["total"] == 2
    assert data["totals_by_case_type"] == {"stockout_risk": 1, "sales_drop": 1}
    assert data["acknowledged_by_case_type"] == {"stockout_risk": 1, "sales_drop": 1}
    assert data["resolved_by_case_type"] == {"stockout_risk": 1}
    assert data["time_to_acknowledge_seconds_by_case_type"]["sales_drop"] == {
        "min": 3600,
        "max": 3600,
        "avg": 3600,
        "median": 3600,
    }


def test_workflow_throughput_rejects_unauthorized_request(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/workflow/throughput",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


def test_workflow_throughput_returns_503_when_auth_not_configured(_isolate_db, monkeypatch):
    from server import app

    monkeypatch.delenv("ORVO_INTERNAL_OPERATOR_TOKEN", raising=False)

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/workflow/throughput",
        headers=AUTH,
    )

    assert response.status_code == 503
    body = response.get_json()
    assert body["error"]["code"] == "internal_auth_not_configured"

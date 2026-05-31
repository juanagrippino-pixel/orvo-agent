"""HTTP endpoint tests for service-management case projections."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import pytest

from app.brain.operational_cases import OperationalCaseDetection
from app.brain.storage import SQLiteOperationalCaseStore, init_schema

AUTH = {"Authorization": "Bearer test-internal-token"}


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 24, hour, minute, tzinfo=timezone.utc)


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
    case_type: str = "data_stale",
    run_id: str = "run-service-management",
    metadata: dict | None = None,
) -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"{business_id}/{case_type}/connector/tiendanube/runtime.service/daily",
        title="Datos demorados token=hidden-secret",
        severity="warning",
        priority_score=80,
        entity_scope={"kind": "connector", "id": "tiendanube", "label": "Tiendanube"},
        evidence_refs=[f"evidence://tiendanube/{business_id}/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        metadata=metadata or {},
    )


def test_internal_service_management_cases_endpoint_returns_scoped_enveloped_projection(_isolate_db):
    from server import app

    with closing(sqlite3.connect(str(_isolate_db))) as conn:
        store = SQLiteOperationalCaseStore(conn)
        waiting = store.upsert_detection(
            _detection(metadata={"waiting_on": "external"}),
            detected_at=_utc(8),
        )
        store.transition_case(
            waiting.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="operator@example.com",
            transitioned_at=_utc(9),
        )
        store.upsert_detection(
            _detection(business_id="other-shop", run_id="run-other"),
            detected_at=_utc(7),
        )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"limit": "1"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["limit"] == 1
    assert data["count"] == 1
    assert data["total"] == 1
    assert data["by_service_record_type"] == {"incident": 1}
    assert data["by_owner_status"] == {"waiting_external": 1}
    row = data["service_cases"][0]
    assert row["case_id"] == waiting.case_id
    assert row["service_record_type"]["code"] == "incident"
    assert row["owner_status"]["code"] == "waiting_external"
    assert row["owner_status"]["source_status"] == "acknowledged"
    assert row["sla"]["first_response"]["policy_key"] == "first_response_warning_240m"
    assert "hidden-secret" not in str(body)


def test_internal_service_management_cases_endpoint_rejects_invalid_limit(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"limit": "not-an-int"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_limit"

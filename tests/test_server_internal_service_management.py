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
            _detection(case_type="stockout_risk", run_id="run-breached"),
            detected_at=_utc(7),
        )
        store.upsert_detection(
            _detection(business_id="other-shop", run_id="run-other"),
            detected_at=_utc(7),
        )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"limit": "1", "sla_status": "paused"},
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
    assert data["unfiltered_total"] == 2
    assert data["filters"] == {"sla_status": "paused"}
    assert data["by_service_record_type"] == {"incident": 2}
    assert data["by_owner_status"] == {"new": 1, "waiting_external": 1}
    assert data["by_sla_status"] == {"breached": 1, "paused": 1}
    row = data["service_cases"][0]
    assert row["case_id"] == waiting.case_id
    assert row["service_record_type"]["code"] == "incident"
    assert row["owner_status"]["code"] == "waiting_external"
    assert row["owner_status"]["status_category"] == "in_progress"
    assert row["owner_status"]["source_status"] == "acknowledged"
    assert row["sla_status"]["code"] == "paused"
    assert row["sla_status"]["active_policy_key"] == "resolution_warning_1440m"
    assert row["sla_status"]["overdue_seconds"] == 0
    assert row["needs_escalation"] is True
    assert {reason["code"] for reason in row["escalation_reasons"]} >= {"waiting_external"}
    assert {"code": "waiting_external", "label_es": "Bloqueado por un tercero", "source": "owner_status"} in row[
        "escalation_reasons"
    ]
    assert row["sla"]["first_response"]["policy_key"] == "first_response_warning_240m"
    assert row["sla"]["first_response"]["overdue_seconds"] == 0
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


def test_internal_service_management_cases_endpoint_filters_by_service_record_type(_isolate_db):
    from server import app

    with closing(sqlite3.connect(str(_isolate_db))) as conn:
        store = SQLiteOperationalCaseStore(conn)
        store.upsert_detection(
            _detection(case_type="stockout_risk", run_id="run-incident"),
            detected_at=_utc(7),
        )
        problem = store.upsert_detection(
            _detection(case_type="sales_drop", run_id="run-problem"),
            detected_at=_utc(8),
        )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"service_record_type": "problem"},
    )

    assert response.status_code == 200
    body = response.get_json()
    data = body["data"]
    assert data["filters"] == {"service_record_type": "problem"}
    assert data["count"] == 1
    assert data["total"] == 1
    assert data["unfiltered_total"] == 2
    assert [row["case_id"] for row in data["service_cases"]] == [problem.case_id]
    assert data["by_service_record_type"] == {"incident": 1, "problem": 1}


def test_internal_service_management_cases_endpoint_filters_by_owner_status(_isolate_db):
    from server import app

    with closing(sqlite3.connect(str(_isolate_db))) as conn:
        store = SQLiteOperationalCaseStore(conn)
        waiting = store.upsert_detection(
            _detection(metadata={"waiting_on": "external"}, run_id="run-owner-waiting"),
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
            _detection(case_type="stockout_risk", run_id="run-owner-new"),
            detected_at=_utc(7),
        )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"owner_status": "waiting_external"},
    )

    assert response.status_code == 200
    body = response.get_json()
    data = body["data"]
    assert data["filters"] == {"owner_status": "waiting_external"}
    assert data["count"] == 1
    assert data["total"] == 1
    assert data["unfiltered_total"] == 2
    assert [row["case_id"] for row in data["service_cases"]] == [waiting.case_id]
    assert data["by_owner_status"] == {"new": 1, "waiting_external": 1}


def test_internal_service_management_cases_endpoint_filters_by_escalation_reason(_isolate_db):
    from server import app

    with closing(sqlite3.connect(str(_isolate_db))) as conn:
        store = SQLiteOperationalCaseStore(conn)
        waiting = store.upsert_detection(
            _detection(metadata={"waiting_on": "external"}, run_id="run-escalation-waiting"),
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
            _detection(case_type="stockout_risk", run_id="run-escalation-new"),
            detected_at=_utc(7),
        )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"escalation_reason": "waiting_external"},
    )

    assert response.status_code == 200
    body = response.get_json()
    data = body["data"]
    assert data["filters"] == {"escalation_reason": "waiting_external"}
    assert data["count"] == 1
    assert data["total"] == 1
    assert data["unfiltered_total"] == 2
    assert [row["case_id"] for row in data["service_cases"]] == [waiting.case_id]
    assert data["by_escalation_reason"] == {
        "first_response_sla_breached": 1,
        "resolution_sla_breached": 1,
        "waiting_external": 1,
    }


def test_internal_service_management_cases_endpoint_filters_by_needs_escalation(_isolate_db):
    from server import app

    with closing(sqlite3.connect(str(_isolate_db))) as conn:
        store = SQLiteOperationalCaseStore(conn)
        escalated = store.upsert_detection(
            _detection(case_type="stockout_risk", run_id="run-needs-escalation"),
            detected_at=_utc(7),
        )
        calm = store.upsert_detection(
            _detection(case_type="sales_drop", run_id="run-no-escalation"),
            detected_at=_utc(11),
        )
        store.transition_case(
            calm.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="operator@example.com",
            transitioned_at=_utc(11, 15),
        )
        store.transition_case(
            calm.case_id,
            status="resolved",
            actor_type="operator",
            actor_ref="operator@example.com",
            reason="Owner confirmed the sales review was handled.",
            transitioned_at=_utc(11, 30),
        )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"needs_escalation": "true"},
    )

    assert response.status_code == 200
    body = response.get_json()
    data = body["data"]
    assert data["filters"] == {"needs_escalation": True}
    assert data["count"] == 1
    assert data["total"] == 1
    assert data["unfiltered_total"] == 2
    assert [row["case_id"] for row in data["service_cases"]] == [escalated.case_id]
    assert data["service_cases"][0]["needs_escalation"] is True


def test_internal_service_management_cases_endpoint_sorts_by_sla_urgency(_isolate_db):
    from server import app

    with closing(sqlite3.connect(str(_isolate_db))) as conn:
        store = SQLiteOperationalCaseStore(conn)
        store.upsert_detection(
            _detection(case_type="stockout_risk", run_id="run-sort-high-priority"),
            detected_at=_utc(11, 50),
        )
        breached = store.upsert_detection(
            _detection(case_type="sales_drop", run_id="run-sort-breached"),
            detected_at=_utc(7),
        )

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"sort": "sla_urgency", "limit": "1"},
    )

    assert response.status_code == 200
    body = response.get_json()
    data = body["data"]
    assert data["sort_by"] == "sla_urgency"
    assert data["count"] == 1
    assert data["total"] == 2
    assert [row["case_id"] for row in data["service_cases"]] == [breached.case_id]
    assert data["service_cases"][0]["sla_status"]["code"] == "breached"


def test_internal_service_management_cases_endpoint_rejects_invalid_sla_status(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"sla_status": "waiting_external"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_sla_status"


def test_internal_service_management_cases_endpoint_rejects_invalid_service_record_type(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"service_record_type": "task"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_service_record_type"


def test_internal_service_management_cases_endpoint_rejects_invalid_owner_status(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"owner_status": "blocked"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_owner_status"


def test_internal_service_management_cases_endpoint_rejects_invalid_escalation_reason(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"escalation_reason": "manager_vibes"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_escalation_reason"


def test_internal_service_management_cases_endpoint_rejects_invalid_needs_escalation(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"needs_escalation": "sometimes"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_needs_escalation"


def test_internal_service_management_cases_endpoint_rejects_invalid_sort(_isolate_db):
    from server import app

    client = app.test_client()
    response = client.get(
        "/internal/brain/businesses/artemea/service-management/cases",
        headers=AUTH,
        query_string={"sort": "manager_vibes"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_sort"

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.brain.operator_audit import SQLiteOperatorAuditStore
from app.brain.storage import init_schema


AUTH = {
    "Authorization": "Bearer test-internal-token",
    "X-Orvo-Operator": "operator:juan",
    "X-Request-ID": "req-test",
}


def _client(monkeypatch, tmp_path):
    db_path = tmp_path / "operator-audit.sqlite3"
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    from server import app

    return app.test_client(), db_path


def _append_event(db_path, *, request_id: str = "req-source") -> None:
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    SQLiteOperatorAuditStore(conn).append_event(
        business_id="artemea",
        actor_ref="operator:seed",
        event_type="operator.case_action.failed",
        target_type="operational_case",
        request_id=request_id,
        data={"error_code": "seed_failure"},
        created_at=datetime.now(timezone.utc),
    )
    conn.close()


def _audit_events(db_path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    events = SQLiteOperatorAuditStore(conn).list_events(business_id="artemea", retention_days=90, limit=20)
    conn.close()
    return events


def test_operator_audit_export_success_writes_read_audit_event(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _append_event(db_path)

    response = client.get(
        "/internal/brain/businesses/artemea/operator-audit-events?limit=10&retention_days=7",
        headers={**AUTH, "X-Orvo-Role": "admin", "X-Orvo-Operator": "admin:sol", "X-Request-ID": "req-audit-export-read"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["count"] == 1
    events_by_request = {event["request_id"]: event for event in _audit_events(db_path)}
    audit_event = events_by_request["req-audit-export-read"]
    assert audit_event["event_type"] == "operator.operator_audit_events.read"
    assert audit_event["target_type"] == "operator_audit_events"
    assert audit_event["target_id"] == "artemea"
    assert audit_event["data"] == {
        "status": "allowed",
        "scope": "business",
        "limit": 10,
        "retention_days": 7,
        "result_count": 1,
    }


def test_operator_audit_export_validation_failure_writes_failed_audit_event(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/operator-audit-events?retention_days=3650",
        headers={
            **AUTH,
            "X-Orvo-Role": "admin",
            "X-Orvo-Operator": "admin:sol",
            "X-Request-ID": "req-audit-export-invalid",
        },
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "invalid_retention_days"
    events_by_request = {event["request_id"]: event for event in _audit_events(db_path)}
    audit_event = events_by_request["req-audit-export-invalid"]
    assert audit_event["event_type"] == "operator.operator_audit_events.read_failed"
    assert audit_event["target_type"] == "operator_audit_events"
    assert audit_event["target_id"] == "artemea"
    assert audit_event["data"] == {
        "status": "failed",
        "scope": "business",
        "error_code": "invalid_retention_days",
        "status_code": 400,
        "method": "GET",
        "limit_present": False,
        "retention_days_present": True,
    }

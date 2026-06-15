from __future__ import annotations

import sqlite3

from app.http.internal_brain import common as common_routes
from app.http.internal_brain import operator_audit as operator_audit_routes


AUTH = {
    "Authorization": "Bearer test-internal-token",
    "X-Orvo-Operator": "operator:juan",
    "X-Request-ID": "req-audit-sink",
}


def _client(monkeypatch, tmp_path):
    db_path = tmp_path / "operator-audit.sqlite3"
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    from server import app

    return app.test_client(), db_path


def test_internal_authorization_denial_audit_sink_failure_keeps_forbidden(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    calls = []

    def broken_append(**kwargs):
        calls.append(kwargs)
        raise sqlite3.Error("audit sink unavailable")

    monkeypatch.setattr(common_routes, "_append_operator_audit_event", broken_append)

    response = client.get(
        "/internal/brain/businesses/artemea/case-actions",
        headers={
            **AUTH,
            "X-Orvo-Businesses": "other",
            "X-Request-ID": "req-audit-sink-business-denied",
        },
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"
    assert calls[0]["event_type"] == "operator.authorization.denied"
    assert calls[0]["data"]["reason"] == "business_scope_denied"
    assert "audit sink unavailable" not in response.get_data(as_text=True)


def test_operator_audit_export_store_failure_writes_failed_audit_event_best_effort(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    calls = []

    def broken_append(**kwargs):
        calls.append(kwargs)
        raise sqlite3.Error("audit sink unavailable")

    monkeypatch.setattr(operator_audit_routes, "_append_operator_audit_event", broken_append)
    monkeypatch.setattr(
        operator_audit_routes,
        "_internal_brain_db_path",
        lambda: str(tmp_path / "missing-parent-directory" / "orvo-brain.sqlite3"),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/operator-audit-events?limit=10&retention_days=7",
        headers={**AUTH, "X-Orvo-Role": "admin", "X-Orvo-Operator": "admin:sol", "X-Request-ID": "req-audit-store-down"},
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "internal_store_unavailable"
    assert [call["event_type"] for call in calls] == ["operator.operator_audit_events.read_failed"]
    assert calls[0]["target_type"] == "operator_audit_events"
    assert calls[0]["target_id"] == "artemea"
    assert calls[0]["data"] == {
        "status": "failed",
        "scope": "business",
        "error_code": "internal_store_unavailable",
        "status_code": 503,
        "limit_present": True,
        "retention_days_present": True,
    }
    assert "audit sink unavailable" not in response.get_data(as_text=True)

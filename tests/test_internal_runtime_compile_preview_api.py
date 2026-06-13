from __future__ import annotations

import json
import sqlite3
from contextlib import closing

from app.brain.config import BusinessConfig, ConnectorConfig, ReportSchedule
from app.brain.storage import SQLiteConfigStore, init_schema

AUTH = {
    "Authorization": "Bearer test-internal-token",
    "X-Orvo-Operator": "operator:juan",
    "X-Request-ID": "req-compile-preview",
}


def _client(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime-compile-preview.sqlite3"
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    from server import app

    return app.test_client(), db_path


def _save_runtime_config(db_path) -> None:
    with closing(sqlite3.connect(db_path)) as conn:
        init_schema(conn)
        store = SQLiteConfigStore(conn)
        store.save_business_config(
            BusinessConfig(
                business_id="artemea",
                business_name="Artemea",
                owner_phone="+5491100000000",
                timezone="America/Argentina/Buenos_Aires",
                currency="ARS",
                connectors=[
                    ConnectorConfig(
                        connector_id="tn-main",
                        connector_type="tiendanube",
                        label="TiendaNube principal",
                        params={"store_id": "123", "access_token": "raw_inline_compile_token"},
                    )
                ],
            )
        )
        store.save_schedule(
            ReportSchedule(
                schedule_id="sched-daily",
                business_id="artemea",
                cron_expression="0 8 * * *",
                report_type="daily",
            )
        )


def _audit_events(db_path) -> list[dict]:
    with closing(sqlite3.connect(db_path)) as conn:
        init_schema(conn)
        rows = conn.execute(
            """
            SELECT event_id, business_id, actor_ref, event_type, target_type,
                   target_id, request_id, created_at, data
            FROM operator_audit_events
            ORDER BY created_at ASC, event_id ASC
            """
        ).fetchall()
    return [
        {
            "event_id": event_id,
            "business_id": row_business_id,
            "actor_ref": actor_ref,
            "event_type": event_type,
            "target_type": target_type,
            "target_id": target_id,
            "request_id": request_id,
            "created_at": created_at,
            "data": json.loads(data),
        }
        for (
            event_id,
            row_business_id,
            actor_ref,
            event_type,
            target_type,
            target_id,
            request_id,
            created_at,
            data,
        ) in rows
    ]


def test_internal_runtime_compile_preview_uses_stored_config_without_secret_or_connector_execution(
    monkeypatch,
    tmp_path,
):
    client, db_path = _client(monkeypatch, tmp_path)
    _save_runtime_config(db_path)

    def fail_if_connector_executes(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("compile-preview must not execute Tiendanube connectors")

    monkeypatch.setattr("server.build_daily_report_from_tiendanube", fail_if_connector_executes)

    response = client.post(
        "/internal/brain/businesses/artemea/runtime/compile-preview",
        json={},
        headers=AUTH,
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_inline_compile_token" not in raw_body
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["request_id"] == "req-compile-preview"
    assert body["redaction_applied"] is True

    data = body["data"]
    runtime = data["runtime"]
    assert runtime["business_id"] == "artemea"
    assert runtime["run_mode"] == "preview"
    assert runtime["execution_plan"] == {
        "daily_connector_types": ["tiendanube"],
        "report_types": ["daily"],
    }
    assert runtime["connectors"][0]["params"] == {"store_id": "123"}
    assert "access_token" not in runtime["connectors"][0]["params"]
    assert runtime["report_schedules"][0]["schedule_id"] == "sched-daily"
    assert data["run_metadata"]["run_mode"] == "preview"
    assert data["validation_errors"] == []


def test_internal_runtime_compile_preview_invalid_payload_writes_redacted_audit_event(
    monkeypatch,
    tmp_path,
):
    client, db_path = _client(monkeypatch, tmp_path)
    _save_runtime_config(db_path)

    response = client.post(
        "/internal/brain/businesses/artemea/runtime/compile-preview",
        headers={
            **AUTH,
            "X-Orvo-Operator": "operator:juan access_token=raw_invalid_actor_secret",
            "X-Request-ID": "req-invalid-runtime-payload",
        },
        json=[],
    )

    assert response.status_code == 400
    raw_body = response.get_data(as_text=True)
    assert "raw_invalid_actor_secret" not in raw_body
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_runtime_compile_preview_payload"
    assert body["redaction_applied"] is True

    events = _audit_events(db_path)
    assert len(events) == 1
    event = events[0]
    assert event["business_id"] == "artemea"
    assert event["actor_ref"] == "[REDACTED]"
    assert event["event_type"] == "operator.runtime_compile_preview.invalid_payload"
    assert event["target_type"] == "runtime_compile_preview"
    assert event["target_id"] == "artemea"
    assert event["request_id"] == "req-invalid-runtime-payload"
    assert event["data"] == {"method": "POST", "payload_type": "list"}
    serialized = json.dumps(event, sort_keys=True)
    assert "raw_invalid_actor_secret" not in serialized


def test_internal_runtime_compile_preview_missing_business_config_is_safe_404(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.post(
        "/internal/brain/businesses/artemea/runtime/compile-preview",
        json={},
        headers=AUTH,
    )

    assert response.status_code == 404
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "business_config_not_found"
    assert body["redaction_applied"] is True

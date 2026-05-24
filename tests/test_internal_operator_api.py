from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.brain.operational_cases import (
    OperationalCaseDetection,
    OperationalCaseSeverity,
    OperationalCaseType,
    SQLiteOperationalCaseStore,
)
from app.brain.run_ledger import ArtifactRef, DispatchOutcomeRef, RunStatus, SQLiteRunLedger
from app.brain.storage import init_schema


AUTH = {"Authorization": "Bearer test-internal-token", "X-Orvo-Operator": "operator:juan", "X-Request-ID": "req-test"}


def _utc(hour: int) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _case_detection(
    *,
    business_id: str = "artemea",
    case_type: OperationalCaseType = "stockout_risk",
    dedupe_suffix: str = "stockout_risk/business/monitored/commerce.inventory/daily",
    priority: int = 100,
    severity: OperationalCaseSeverity = "critical",
    title: str = "Stock crítico",
    run_id: str = "run-artemea-1",
) -> OperationalCaseDetection:
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title=title,
        severity=severity,
        priority_score=priority,
        entity_scope={"kind": "business", "id": "monitored", "label": "Monitoreado"},
        evidence_refs=[f"evidence://{business_id}/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        metadata={"source": "test"},
    )


def _seed_case(db_path, detection: OperationalCaseDetection):
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    case = store.upsert_detection(detection, detected_at=_utc(8))
    conn.close()
    return case


def _seed_run(db_path, *, business_id: str, run_id: str, status: RunStatus = "succeeded"):
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    ledger = SQLiteRunLedger(conn)
    run = ledger.create_run(
        business_id=business_id,
        trigger_type="forced",
        run_id=run_id,
        started_at=_utc(7),
        config_ref="config://runtime?access_token=raw_run_secret",
        summary_metadata={"note": "Bearer raw_run_secret"},
    )
    ledger.append_artifact_ref(
        run.run_id,
        ArtifactRef(
            artifact_id=f"{run_id}:daily_report",
            artifact_type="daily_report",
            uri="ledger://artifact?api_key=raw_artifact_secret",
            operational_case_ids=[f"case-for-{run_id}"],
        ),
    )
    ledger.append_dispatch_outcome(
        run.run_id,
        DispatchOutcomeRef(
            channel="whatsapp",
            status="sent",
            message_id="wamid.safe",
            provider_response_ref="provider://response?access_token=raw_provider_secret",
        ),
    )
    ledger.update_run(run.run_id, status=status, finished_at=_utc(8), summary_metadata={"cases_opened": 1})
    conn.close()
    return run


def _client(monkeypatch, tmp_path):
    db_path = tmp_path / "operator.sqlite3"
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    from server import app

    return app.test_client(), db_path


def test_internal_case_queue_returns_envelope_scoped_and_priority_ordered(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    warning = _case_detection(
        case_type="sales_drop",
        dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        priority=70,
        severity="warning",
        title="Ventas bajaron",
        run_id="run-artemea-warn",
    )
    critical = _case_detection(run_id="run-artemea-critical")
    other = _case_detection(business_id="other", run_id="run-other")
    warning_case = _seed_case(db_path, warning)
    critical_case = _seed_case(db_path, critical)
    _seed_case(db_path, other)

    response = client.get("/internal/brain/businesses/artemea/cases?status=open", headers=AUTH)

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["request_id"] == "req-test"
    assert body["redaction_applied"] is True
    assert [item["case_id"] for item in body["data"]["cases"]] == [critical_case.case_id, warning_case.case_id]
    assert all(item["business_id"] == "artemea" for item in body["data"]["cases"])
    assert body["data"]["cases"][0]["evidence_count"] == 1


def test_internal_case_detail_cannot_cross_business_scope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    other_case = _seed_case(db_path, _case_detection(business_id="other", run_id="run-other"))

    response = client.get(f"/internal/brain/businesses/artemea/cases/{other_case.case_id}", headers=AUTH)

    assert response.status_code == 404
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "case_not_found"
    assert body["redaction_applied"] is True


def test_internal_case_action_rejects_unknown_key_without_mutation(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers=AUTH,
        json={"action_key": "delete_everything"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "unknown_action_key"
    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.status == "open"
    assert len(reloaded.timeline) == len(case.timeline)


def test_internal_case_actions_acknowledge_and_resolve_with_actor_and_redaction(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    ack = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers=AUTH,
        json={"action_key": "acknowledge_case", "reason": "Estoy encima"},
    )
    assert ack.status_code == 200
    assert ack.get_json()["data"]["case"]["status"] == "acknowledged"

    resolved = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers=AUTH,
        json={"action_key": "resolve_case", "reason": "Fixed access_token=raw_action_secret"},
    )

    assert resolved.status_code == 200
    raw_body = resolved.get_data(as_text=True)
    assert "raw_action_secret" not in raw_body
    body = resolved.get_json()
    assert body["data"]["case"]["status"] == "resolved"
    assert body["redaction_applied"] is True

    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.status == "resolved"
    assert reloaded.timeline[-1].actor_ref == "operator:juan"
    assert "raw_action_secret" not in reloaded.model_dump_json()


def test_internal_run_history_and_detail_are_business_scoped_and_redacted(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_run(db_path, business_id="artemea", run_id="run-artemea")
    other = _seed_run(db_path, business_id="other", run_id="run-other")

    list_response = client.get("/internal/brain/businesses/artemea/runs", headers=AUTH)
    assert list_response.status_code == 200
    list_body = list_response.get_json()
    assert [run["run_id"] for run in list_body["data"]["runs"]] == ["run-artemea"]
    assert "raw_run_secret" not in list_response.get_data(as_text=True)

    detail_response = client.get("/internal/brain/businesses/artemea/runs/run-artemea", headers=AUTH)
    assert detail_response.status_code == 200
    assert detail_response.get_json()["data"]["run"]["run_id"] == "run-artemea"
    raw_detail = detail_response.get_data(as_text=True)
    assert "raw_run_secret" not in raw_detail
    assert "raw_artifact_secret" not in raw_detail
    assert "raw_provider_secret" not in raw_detail

    cross = client.get(f"/internal/brain/businesses/artemea/runs/{other.run_id}", headers=AUTH)
    assert cross.status_code == 404
    assert cross.get_json()["error"]["code"] == "run_not_found"


def test_internal_endpoints_require_configured_bearer_token(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection())

    missing = client.get("/internal/brain/businesses/artemea/cases")
    wrong = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers={"Authorization": "Bearer wrong", "X-Orvo-Operator": "operator:juan"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.get_json()["error"]["code"] == "unauthorized"

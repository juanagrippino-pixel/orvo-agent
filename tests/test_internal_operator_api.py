from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from app.brain.operational_cases import (
    OperationalCaseDetection,
    OperationalCaseEvidenceMetric,
    OperationalCaseEvidenceSnapshot,
    OperationalCaseSeverity,
    OperationalCaseType,
    SQLiteOperationalCaseStore,
)
from app.brain.run_ledger import ArtifactRef, DispatchOutcomeRef, RunStatus, SQLiteRunLedger
from app.brain.storage import init_schema


AUTH = {"Authorization": "Bearer test-internal-token", "X-Orvo-Operator": "operator:juan", "X-Request-ID": "req-test"}
VIEWER_AUTH = {**AUTH, "X-Orvo-Role": "viewer", "X-Orvo-Operator": "viewer:ana"}


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
    source: str = "tiendanube",
    source_label: str = "Tiendanube access_token=raw_snapshot_secret",
    freshness_state: str = "fresh",
    entity_scope: dict[str, str] | None = None,
) -> OperationalCaseDetection:
    scope = entity_scope or {"kind": "business", "id": "monitored", "label": "Monitoreado"}
    return OperationalCaseDetection(
        business_id=business_id,
        case_type=case_type,
        dedupe_key=f"{business_id}/{dedupe_suffix}",
        title=title,
        severity=severity,
        priority_score=priority,
        entity_scope=scope,
        evidence_refs=[f"evidence://{business_id}/{run_id}/{case_type}"],
        run_id=run_id,
        artifact_refs=[f"ledger://runs/{run_id}/daily-report"],
        evidence_snapshots=[
            OperationalCaseEvidenceSnapshot(
                snapshot_key=f"{run_id}/evidence://{business_id}/{run_id}/{case_type}/{case_type}/{scope.get('kind', 'unknown')}/{scope.get('id', 'unknown')}",
                captured_at=_utc(8),
                run_id=run_id,
                artifact_ref=f"ledger://runs/{run_id}/daily-report?access_token=raw_snapshot_secret",
                evidence_ref=f"evidence://{business_id}/{run_id}/{case_type}?api_key=raw_snapshot_secret",
                source=source,
                source_label=source_label,
                case_type=case_type,
                entity_scope=scope,
                summary="Snapshot Bearer raw_snapshot_secret",
                freshness_state=freshness_state,  # type: ignore[arg-type]
                metrics=[
                    OperationalCaseEvidenceMetric(
                        metric_key="commerce.inventory.available_units",
                        label="Stock access_token=raw_snapshot_secret",
                        value=3,
                        unit="units",
                        observed_at=_utc(8),
                        metadata={"api_key": "raw_snapshot_secret"},
                    )
                ],
                metadata={"source": "test", "access_token": "raw_snapshot_secret"},
            )
        ],
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
    assert body["data"]["cases"][0]["evidence_snapshot_count"] == 1
    assert body["data"]["cases"][0]["latest_evidence_at"] == "2026-05-24T08:00:00Z"
    assert body["data"]["cases"][0]["source_connectors"] == ["tiendanube"]
    assert body["data"]["cases"][0]["degraded"] is False


def test_internal_case_titles_are_redacted_in_queue_and_detail(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(
        db_path,
        _case_detection(title="Stock crítico access_token=raw_case_title_secret"),
    )

    queue_response = client.get("/internal/brain/businesses/artemea/cases?status=open", headers=AUTH)
    detail_response = client.get(f"/internal/brain/businesses/artemea/cases/{case.case_id}", headers=AUTH)

    assert queue_response.status_code == 200
    assert detail_response.status_code == 200
    assert "raw_case_title_secret" not in queue_response.get_data(as_text=True)
    assert "raw_case_title_secret" not in detail_response.get_data(as_text=True)
    queue_case = queue_response.get_json()["data"]["cases"][0]
    detail_case = detail_response.get_json()["data"]["case"]
    assert queue_case["title"] == "Stock crítico access_token=[REDACTED]"
    assert detail_case["title"] == "Stock crítico access_token=[REDACTED]"
    assert detail_case["timeline"][0]["summary"] == "Opened stockout_risk case from deterministic detection."


def test_internal_case_detail_returns_explicit_evidence_and_timeline_projection(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.get(f"/internal/brain/businesses/artemea/cases/{case.case_id}", headers=AUTH)

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_snapshot_secret" not in raw_body
    body = response.get_json()
    detail = body["data"]["case"]
    assert detail["case_id"] == case.case_id
    assert detail["evidence_snapshot_count"] == 1
    assert detail["evidence_snapshots"][0]["source"] == "tiendanube"
    assert detail["evidence_snapshots"][0]["freshness_state"] == "fresh"
    assert detail["evidence_snapshots"][0]["metrics"][0]["metric_key"] == "commerce.inventory.available_units"
    assert detail["evidence_snapshots"][0]["metrics"][0]["value"] == 3
    assert detail["timeline"][0]["case_id"] == case.case_id
    assert detail["timeline"][0]["evidence_snapshot_ids"] == [case.evidence_snapshots[0].snapshot_id]
    assert detail["timeline"][0]["artifact_ref"] == "ledger://runs/run-artemea-1/daily-report"
    assert body["redaction_applied"] is True


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


def test_internal_case_action_cannot_cross_business_scope_or_mutate_foreign_case(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    other_case = _seed_case(db_path, _case_detection(business_id="other", run_id="run-other"))

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{other_case.case_id}/actions",
        headers=AUTH,
        json={"action_key": "acknowledge_case"},
    )

    assert response.status_code == 404
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "case_not_found"
    assert body["redaction_applied"] is True

    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(other_case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.business_id == "other"
    assert reloaded.status == "open"
    assert len(reloaded.timeline) == len(other_case.timeline)
    assert all(event.actor_ref != "operator:juan" for event in reloaded.timeline)


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


def test_internal_case_action_actor_identity_comes_from_authenticated_header(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())
    headers = {**AUTH, "X-Orvo-Operator": "operator:trusted"}

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers=headers,
        json={
            "action_key": "add_comment",
            "comment": "Revisado por operaciones",
            "actor": "operator:payload-spoof",
            "actor_ref": "operator:payload-spoof-ref",
        },
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "operator:payload-spoof" not in raw_body
    body = response.get_json()
    latest_event = body["data"]["case"]["timeline"][-1]
    assert latest_event["event_type"] == "operator_comment"
    assert latest_event["actor_ref"] == "operator:trusted"

    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.timeline[-1].actor_ref == "operator:trusted"
    assert all("payload-spoof" not in event.actor_ref for event in reloaded.timeline)


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


def test_internal_case_action_assign_owner_uses_owner_ref_alias_and_redacts(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers=AUTH,
        json={"action_key": "assign_owner", "owner_ref": "dueña access_token=raw_owner_secret"},
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_owner_secret" not in raw_body
    body = response.get_json()
    assigned = body["data"]["case"]
    assert assigned["status"] == "open"
    assert assigned["assignee_ref"] == "dueña access_token=[REDACTED]"
    assert assigned["assigned_at"] is not None
    assert assigned["timeline"][-1]["event_type"] == "case_assigned"
    assert assigned["timeline"][-1]["metadata"] == {"assignee_ref": "dueña access_token=[REDACTED]"}
    assert body["redaction_applied"] is True

    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.assignee_ref == "dueña access_token=[REDACTED]"
    assert reloaded.status == "open"
    assert "raw_owner_secret" not in reloaded.model_dump_json()


def test_internal_case_action_catalog_returns_canonical_action_contract(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)

    response = client.get("/internal/brain/businesses/artemea/case-actions", headers=AUTH)

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["request_id"] == "req-test"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["api_enabled_action_keys"] == [
        "acknowledge_case",
        "add_comment",
        "assign_owner",
        "dismiss_case",
        "mark_in_progress",
        "resolve_case",
    ]
    assert data["operator_executable_action_keys"] == data["api_enabled_action_keys"]
    actions = {item["action_key"]: item for item in data["actions"]}
    assert actions["acknowledge_case"]["operator_executable"] is True
    assert actions["acknowledge_case"]["status_effect"] == "acknowledged"
    assert actions["add_comment"]["requires_comment"] is True
    assert actions["assign_owner"]["input_fields"] == ["assignee_ref"]
    assert actions["resolve_case"]["requires_reason"] is True
    assert actions["dismiss_case"]["requires_reason"] is True
    assert actions["request_external_action"]["api_enabled"] is False
    assert actions["request_external_action"]["approval_required"] is True
    assert "raw_" not in response.get_data(as_text=True)


def test_internal_case_action_catalog_marks_viewer_actions_not_executable(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)

    response = client.get("/internal/brain/businesses/artemea/case-actions", headers=VIEWER_AUTH)

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["api_enabled_action_keys"] == [
        "acknowledge_case",
        "add_comment",
        "assign_owner",
        "dismiss_case",
        "mark_in_progress",
        "resolve_case",
    ]
    assert data["operator_executable_action_keys"] == []
    actions = {item["action_key"]: item for item in data["actions"]}
    assert actions["acknowledge_case"]["api_enabled"] is True
    assert actions["acknowledge_case"]["operator_executable"] is False
    assert actions["acknowledge_case"]["disabled_reason"] == "missing_case_action_permission"
    assert actions["request_external_action"]["operator_executable"] is False
    assert actions["request_external_action"]["disabled_reason"] == "api_disabled"


def test_internal_case_action_catalog_requires_bearer_token(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)

    response = client.get("/internal/brain/businesses/artemea/case-actions")

    assert response.status_code == 401
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "unauthorized"
    assert body["redaction_applied"] is True


def test_internal_operator_session_projects_viewer_permissions_and_redacts_actor(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/operator-session",
        headers={**VIEWER_AUTH, "X-Orvo-Operator": "viewer:ana access_token=raw_operator_secret"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["data"] == {
        "operator": {
            "actor_ref": "[REDACTED]",
            "role": "viewer",
            "permissions": ["internal:read"],
            "can_read_internal": True,
            "can_mutate_cases": False,
        }
    }
    assert "raw_operator_secret" not in response.get_data(as_text=True)


def test_internal_operator_session_defaults_legacy_callers_to_operator_role(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)

    response = client.get("/internal/brain/businesses/artemea/operator-session", headers=AUTH)

    assert response.status_code == 200
    operator = response.get_json()["data"]["operator"]
    assert operator["role"] == "operator"
    assert operator["permissions"] == ["case:action", "internal:read"]
    assert operator["can_mutate_cases"] is True


def test_internal_read_allows_viewer_role(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.get(f"/internal/brain/businesses/artemea/cases/{case.case_id}", headers=VIEWER_AUTH)

    assert response.status_code == 200
    assert response.get_json()["data"]["case"]["case_id"] == case.case_id


def test_internal_case_action_rejects_viewer_role_without_mutation(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers=VIEWER_AUTH,
        json={"action_key": "acknowledge_case"},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body["error"]["code"] == "forbidden"
    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.status == "open"


def test_internal_read_rejects_unknown_role(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.get(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}",
        headers={**AUTH, "X-Orvo-Role": "superuser"},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body["error"]["code"] == "forbidden"


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


def test_internal_case_queue_summary_returns_status_severity_and_actionable_counts(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    critical = _case_detection(run_id="run-artemea-critical")
    warning = _case_detection(
        case_type="sales_drop",
        dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        priority=70,
        severity="warning",
        title="Ventas bajaron",
        run_id="run-artemea-warn",
    )
    other = _case_detection(business_id="other", run_id="run-other")
    _seed_case(db_path, critical)
    _seed_case(db_path, warning)
    _seed_case(db_path, other)

    response = client.get("/internal/brain/businesses/artemea/cases/summary", headers=AUTH)

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    summary = body["data"]
    assert summary["business_id"] == "artemea"
    # Only artemea cases counted (2), not the 'other' business one
    assert summary["total"] == 2
    assert summary["by_severity"]["critical"] == 1
    assert summary["by_severity"]["warning"] == 1
    assert summary["by_case_type"]["stockout_risk"] == 1
    assert summary["by_case_type"]["sales_drop"] == 1
    # Both are open (actionable)
    assert summary["actionable_total"] == 2
    assert summary["actionable_by_severity"]["critical"] == 1
    assert summary["actionable_by_severity"]["warning"] == 1


def test_internal_case_queue_summary_empty_store_returns_zero_counts(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)

    response = client.get("/internal/brain/businesses/artemea/cases/summary", headers=AUTH)

    assert response.status_code == 200
    body = response.get_json()
    summary = body["data"]
    assert summary["total"] == 0
    assert summary["actionable_total"] == 0
    assert summary["actionable_degraded"] == 0
    assert summary["by_status"] == {}
    assert summary["by_severity"] == {}


def test_internal_case_queue_summary_by_priority_bracket_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-artemea-high", priority=95))
    _seed_case(
        db_path,
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            priority=70,
            severity="warning",
            title="Ventas bajaron",
            run_id="run-artemea-medium",
        ),
    )
    _seed_case(db_path, _case_detection(business_id="other", run_id="run-other-high", priority=95))

    response = client.get(
        "/internal/brain/businesses/artemea/cases/summary/by-priority-bracket",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    summary = body["data"]
    assert summary["business_id"] == "artemea"
    assert summary["total"] == 2
    assert summary["actionable_total"] == 2
    assert summary["totals_by_priority_bracket"] == {"high": 1, "medium": 1}
    assert summary["actionable_by_priority_bracket"] == {"high": 1, "medium": 1}
    assert summary["actionable_degraded_by_priority_bracket"] == {}


def test_internal_case_queue_summary_by_case_type_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-artemea-stockout"))
    _seed_case(
        db_path,
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            priority=70,
            severity="warning",
            title="Ventas bajaron",
            run_id="run-artemea-sales-drop",
        ),
    )
    _seed_case(db_path, _case_detection(business_id="other", run_id="run-other-stockout"))

    response = client.get(
        "/internal/brain/businesses/artemea/cases/summary/by-case-type",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    summary = body["data"]
    assert summary["business_id"] == "artemea"
    assert summary["total"] == 2
    assert summary["actionable_total"] == 2
    assert summary["totals_by_case_type"] == {"stockout_risk": 1, "sales_drop": 1}
    assert summary["actionable_by_case_type"] == {"stockout_risk": 1, "sales_drop": 1}
    assert summary["actionable_degraded_by_case_type"] == {}


def test_internal_case_queue_summary_by_source_connector_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-artemea-tn", source="tiendanube"))
    _seed_case(
        db_path,
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            priority=70,
            severity="warning",
            title="Ventas bajaron",
            run_id="run-artemea-sheets",
            source="google_sheets",
            source_label="Google Sheets",
        ),
    )
    _seed_case(db_path, _case_detection(business_id="other", run_id="run-other-tn", source="tiendanube"))

    response = client.get(
        "/internal/brain/businesses/artemea/cases/summary/by-source-connector",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    summary = body["data"]
    assert summary["business_id"] == "artemea"
    assert summary["total"] == 2
    assert summary["actionable_total"] == 2
    assert summary["totals_by_source_connector"] == {"tiendanube": 1, "google_sheets": 1}
    assert summary["actionable_by_source_connector"] == {"tiendanube": 1, "google_sheets": 1}
    assert summary["actionable_degraded_by_source_connector"] == {}


def test_internal_case_queue_summary_by_entity_kind_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(
        db_path,
        _case_detection(
            run_id="run-artemea-product",
            dedupe_suffix="stockout_risk/product/sku-1/commerce.inventory/daily",
            entity_scope={"kind": "product", "id": "sku-1", "label": "SKU 1"},
        ),
    )
    _seed_case(
        db_path,
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            priority=70,
            severity="warning",
            title="Ventas bajaron",
            run_id="run-artemea-channel",
            entity_scope={"kind": "channel", "id": "all", "label": "All channels"},
        ),
    )
    _seed_case(
        db_path,
        _case_detection(
            business_id="other",
            run_id="run-other-product",
            dedupe_suffix="stockout_risk/product/sku-other/commerce.inventory/daily",
            entity_scope={"kind": "product", "id": "sku-other", "label": "Other SKU"},
        ),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/cases/summary/by-entity-kind",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    summary = body["data"]
    assert summary["business_id"] == "artemea"
    assert summary["total"] == 2
    assert summary["actionable_total"] == 2
    assert summary["totals_by_entity_kind"] == {"product": 1, "channel": 1}
    assert summary["actionable_by_entity_kind"] == {"product": 1, "channel": 1}
    assert summary["actionable_degraded_by_entity_kind"] == {}


def test_internal_case_queue_aging_by_priority_bracket_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.upsert_detection(
        _case_detection(run_id="run-artemea-high", priority=95),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-high",
            priority=95,
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/aging/by-priority-bracket",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["actionable_total"] == 1
    assert data["by_age_bucket"]["under_6h"] == 1
    assert data["by_age_bucket_priority_bracket"]["under_6h"] == {"high": 1}
    assert data["oldest_actionable"]["case_type"] == "stockout_risk"


def test_internal_case_queue_aging_by_severity_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.upsert_detection(
        _case_detection(
            run_id="run-artemea-critical",
            severity="critical",
            dedupe_suffix="stockout_risk/product/sku-critical/commerce.inventory/daily",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    store.upsert_detection(
        _case_detection(
            run_id="run-artemea-warning",
            severity="warning",
            dedupe_suffix="stockout_risk/product/sku-warning/commerce.inventory/daily",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-critical",
            severity="critical",
            dedupe_suffix="stockout_risk/product/sku-other/commerce.inventory/daily",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/aging/by-severity",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["actionable_total"] == 2
    assert data["by_age_bucket"]["under_6h"] == 2
    assert data["by_age_bucket_severity"]["under_6h"] == {"critical": 1, "warning": 1}
    assert data["oldest_actionable"]["case_type"] == "stockout_risk"
    assert data["oldest_actionable"]["severity"] in {"critical", "warning"}


def test_internal_case_queue_aging_by_case_type_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.upsert_detection(
        _case_detection(
            run_id="run-artemea-stockout",
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/product/sku-stockout/commerce.inventory/daily",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    store.upsert_detection(
        _case_detection(
            run_id="run-artemea-sales-drop",
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-stockout",
            case_type="stockout_risk",
            dedupe_suffix="stockout_risk/product/sku-other/commerce.inventory/daily",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/aging/by-case-type",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["actionable_total"] == 2
    assert data["by_age_bucket"]["under_6h"] == 2
    assert data["by_age_bucket_case_type"]["under_6h"] == {"stockout_risk": 1, "sales_drop": 1}
    assert data["oldest_actionable"]["case_type"] in {"stockout_risk", "sales_drop"}


def test_internal_case_queue_stagnation_by_priority_bracket_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.upsert_detection(
        _case_detection(run_id="run-artemea-high", priority=95),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-high",
            priority=95,
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/stagnation/by-priority-bracket",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["actionable_total"] == 1
    assert data["by_idle_bucket"]["under_6h"] == 1
    assert data["by_idle_bucket_priority_bracket"]["under_6h"] == {"high": 1}
    assert data["most_stalled_actionable"]["case_type"] == "stockout_risk"


def test_internal_workflow_throughput_by_severity_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    critical = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-critical-throughput",
            severity="critical",
            dedupe_suffix="stockout_risk/product/sku-critical-throughput/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        critical.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        critical.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=3),
    )
    warning = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-warning-throughput",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        warning.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=2),
    )
    store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-critical-throughput",
            severity="critical",
            dedupe_suffix="stockout_risk/product/sku-other-throughput/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/workflow/throughput/by-severity",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["total"] == 2
    assert data["totals_by_severity"] == {"critical": 1, "warning": 1}
    assert data["acknowledged_by_severity"] == {"critical": 1, "warning": 1}
    assert data["resolved_by_severity"] == {"critical": 1}
    assert data["time_to_acknowledge_seconds_by_severity"] == {
        "critical": {"min": 3600, "max": 3600, "avg": 3600, "median": 3600},
        "warning": {"min": 7200, "max": 7200, "avg": 7200, "median": 7200},
    }
    assert data["time_to_resolve_seconds_by_severity"] == {
        "critical": {"min": 10800, "max": 10800, "avg": 10800, "median": 10800}
    }


def test_internal_top_actionable_by_age_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    newest = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-newest",
            dedupe_suffix="stockout_risk/product/sku-newest/commerce.inventory/daily",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    oldest = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            run_id="run-artemea-oldest",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            priority=70,
            severity="warning",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(days=4),
    )
    store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-oldest",
            dedupe_suffix="stockout_risk/product/sku-other/commerce.inventory/daily",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(days=20),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/top-by-age?limit=1",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["actionable_total"] == 2
    assert data["limit"] == 1
    assert data["count"] == 1
    assert data["cases"][0]["case_id"] == oldest.case_id
    assert data["cases"][0]["case_type"] == "sales_drop"
    assert newest.case_id not in {case["case_id"] for case in data["cases"]}


def test_internal_top_stalled_actionable_cases_endpoint_orders_by_idle_time(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    reference = datetime.now(timezone.utc)
    moved = store.upsert_detection(
        _case_detection(
            case_type="stockout_risk",
            run_id="run-artemea-moved",
            dedupe_suffix="stockout_risk/product/sku-moved/commerce.inventory/daily",
        ),
        detected_at=reference - timedelta(days=7),
    )
    store.transition_case(
        moved.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=reference - timedelta(hours=1),
    )
    untouched = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            run_id="run-artemea-untouched",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            priority=70,
            severity="warning",
        ),
        detected_at=reference - timedelta(days=2),
    )
    store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-stalled",
            dedupe_suffix="stockout_risk/product/sku-other/commerce.inventory/daily",
        ),
        detected_at=reference - timedelta(days=20),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/top-stalled?limit=2",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["actionable_total"] == 2
    assert data["limit"] == 2
    assert data["count"] == 2
    assert [case["case_id"] for case in data["cases"]] == [untouched.case_id, moved.case_id]
    assert data["cases"][0]["idle_seconds"] > data["cases"][1]["idle_seconds"]
    assert data["cases"][1]["age_seconds"] > data["cases"][1]["idle_seconds"]


def test_internal_top_degraded_actionable_cases_endpoint_is_scoped_and_ordered(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    high = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-high-degraded",
            priority=95,
            freshness_state="degraded",
            dedupe_suffix="stockout_risk/product/sku-high/commerce.inventory/daily",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    low = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            run_id="run-artemea-low-stale",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            priority=70,
            severity="warning",
            freshness_state="stale",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    store.upsert_detection(
        _case_detection(
            run_id="run-artemea-fresh",
            priority=100,
            freshness_state="fresh",
            dedupe_suffix="stockout_risk/product/sku-fresh/commerce.inventory/daily",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-degraded",
            freshness_state="missing",
            dedupe_suffix="stockout_risk/product/sku-other/commerce.inventory/daily",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(days=3),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/top-degraded?limit=2",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["actionable_degraded_total"] == 2
    assert data["limit"] == 2
    assert data["count"] == 2
    assert [case["case_id"] for case in data["cases"]] == [high.case_id, low.case_id]
    assert [case["freshness_state"] for case in data["cases"]] == ["degraded", "stale"]
    assert all(case["source_connectors"] == ["tiendanube"] for case in data["cases"])


def test_internal_dashboard_endpoint_rejects_non_integer_limit_with_safe_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection())

    response = client.get(
        "/internal/brain/businesses/artemea/dashboard?limit=not-an-int",
        headers=AUTH,
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "invalid_limit"
    assert body["error"]["message"] == "limit must be an integer"
    assert body["redaction_applied"] is True


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


def _audit_events(db_path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT event_id, business_id, actor_ref, event_type, target_type,
               target_id, request_id, data
        FROM operator_audit_events
        ORDER BY created_at ASC, event_id ASC
        """
    ).fetchall()
    conn.close()
    return [
        {
            "event_id": event_id,
            "business_id": business_id,
            "actor_ref": actor_ref,
            "event_type": event_type,
            "target_type": target_type,
            "target_id": target_id,
            "request_id": request_id,
            "data": json.loads(data),
        }
        for event_id, business_id, actor_ref, event_type, target_type, target_id, request_id, data in rows
    ]


def test_internal_case_action_denial_writes_redacted_operator_audit_event(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={**VIEWER_AUTH, "X-Request-ID": "req-denied"},
        json={
            "action_key": "acknowledge_case",
            "metadata": {"api_key": "raw_audit_secret"},
        },
    )

    assert response.status_code == 403
    raw_response = response.get_data(as_text=True)
    assert "raw_audit_secret" not in raw_response
    events = _audit_events(db_path)
    assert len(events) == 1
    event = events[0]
    assert event["business_id"] == "artemea"
    assert event["actor_ref"] == "viewer:ana"
    assert event["event_type"] == "operator.case_action.denied"
    assert event["target_type"] == "operational_case"
    assert event["target_id"] == case.case_id
    assert event["request_id"] == "req-denied"
    assert event["data"]["action_key"] == "acknowledge_case"
    assert event["data"]["permission"] == "case:action"
    assert event["data"]["status_code"] == 403
    assert event["data"]["payload"]["metadata"]["api_key"] == "[REDACTED]"
    assert "raw_audit_secret" not in json.dumps(event, sort_keys=True)


def test_internal_case_action_failure_writes_redacted_operator_audit_event(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={**AUTH, "X-Orvo-Role": "operator", "X-Request-ID": "req-failed"},
        json={
            "action_key": "unknown_action",
            "comment": "Authorization: Basic cmF3X2F1ZGl0X3NlY3JldA==",
            "metadata": {"access_token": "raw_audit_secret"},
        },
    )

    assert response.status_code == 400
    raw_response = response.get_data(as_text=True)
    assert "raw_audit_secret" not in raw_response
    assert "cmF3X2F1ZGl0X3NlY3JldA==" not in raw_response
    events = _audit_events(db_path)
    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "operator.case_action.failed"
    assert event["business_id"] == "artemea"
    assert event["actor_ref"] == "operator:juan"
    assert event["target_id"] == case.case_id
    assert event["request_id"] == "req-failed"
    assert event["data"]["action_key"] == "unknown_action"
    assert event["data"]["error_code"] == "unknown_action_key"
    assert event["data"]["status_code"] == 400
    serialized = json.dumps(event, sort_keys=True)
    assert "raw_audit_secret" not in serialized
    assert "cmF3X2F1ZGl0X3NlY3JldA==" not in serialized


def test_internal_case_action_allows_operator_and_admin_but_not_viewer(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    viewer_case = _seed_case(db_path, _case_detection(run_id="run-viewer"))
    operator_case = _seed_case(db_path, _case_detection(run_id="run-operator", dedupe_suffix="operator/case"))
    admin_case = _seed_case(db_path, _case_detection(run_id="run-admin", dedupe_suffix="admin/case"))

    viewer = client.post(
        f"/internal/brain/businesses/artemea/cases/{viewer_case.case_id}/actions",
        headers=VIEWER_AUTH,
        json={"action_key": "acknowledge_case"},
    )
    operator = client.post(
        f"/internal/brain/businesses/artemea/cases/{operator_case.case_id}/actions",
        headers={**AUTH, "X-Orvo-Role": "operator"},
        json={"action_key": "acknowledge_case"},
    )
    admin = client.post(
        f"/internal/brain/businesses/artemea/cases/{admin_case.case_id}/actions",
        headers={**AUTH, "X-Orvo-Role": "admin", "X-Orvo-Operator": "admin:sol"},
        json={"action_key": "acknowledge_case"},
    )

    assert viewer.status_code == 403
    assert operator.status_code == 200
    assert admin.status_code == 200
    conn = sqlite3.connect(db_path)
    store = SQLiteOperationalCaseStore(conn)
    assert store.get_case(viewer_case.case_id).status == "open"  # type: ignore[union-attr]
    assert store.get_case(operator_case.case_id).status == "acknowledged"  # type: ignore[union-attr]
    assert store.get_case(admin_case.case_id).status == "acknowledged"  # type: ignore[union-attr]
    conn.close()

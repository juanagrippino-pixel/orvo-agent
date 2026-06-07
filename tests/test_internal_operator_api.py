from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from app.brain.operational_cases import (
    OperationalCaseDetection,
    OperationalCaseEvidenceMetric,
    OperationalCaseEvidenceSnapshot,
    OperationalCaseSeverity,
    OperationalCaseType,
    SQLiteOperationalCaseStore,
)
from app.brain.operator_audit import SQLiteOperatorAuditStore
from app.brain.run_ledger import ArtifactRef, DispatchOutcomeRef, RunStatus, SQLiteRunLedger
from app.brain.storage import init_schema


AUTH = {
    "Authorization": "Bearer test-internal-token",
    "X-Orvo-Operator": "operator:juan",
    "X-Request-ID": "req-test",
    "X-Idempotency-Key": "case-action:artemea:test",
}
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


def test_internal_service_catalog_returns_gateway_scoped_manifest(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/service-catalog",
        headers={**VIEWER_AUTH, "X-Orvo-Businesses": "artemea"},
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True).lower()
    assert "access_token" not in raw_body
    assert "secret://" not in raw_body
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    assert body["data"]["schema_version"] == "2026-05-31.service-catalog.v1"
    component_ids = [component["component_id"] for component in body["data"]["components"]]
    assert "edge_developer_platform" in component_ids
    assert "gateway_policy" in component_ids


def test_internal_service_catalog_enforces_gateway_policy_before_projection(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)
    evaluated_contexts = []

    class DenyingGatewayRegistry:
        def evaluate(self, context):
            evaluated_contexts.append(context)
            return SimpleNamespace(
                allowed=False,
                code="gateway_catalog_denied",
                reason="Gateway catalog test denial.",
                status_code=429,
            )

    import app.http.internal_brain.common as internal_common
    import app.http.internal_brain.service_catalog as service_catalog_routes

    monkeypatch.setattr(internal_common, "default_gateway_policy_registry", lambda: DenyingGatewayRegistry())
    monkeypatch.setattr(
        service_catalog_routes,
        "service_catalog_manifest",
        lambda: (_ for _ in ()).throw(AssertionError("manifest should not be projected after gateway denial")),
    )

    response = client.get("/internal/brain/businesses/artemea/service-catalog", headers=AUTH)

    assert response.status_code == 429
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "gateway_catalog_denied"
    assert [context.route_key for context in evaluated_contexts] == ["operator_api.service_catalog.read"]


def test_internal_success_envelope_redacts_secret_shaped_request_id(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection())

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers={**AUTH, "X-Request-ID": "req-safe access_token=raw_request_id_secret"},
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_request_id_secret" not in raw_body
    body = response.get_json()
    assert body["request_id"] == "[REDACTED]"
    assert body["redaction_applied"] is True


def test_internal_error_envelope_and_audit_redact_secret_shaped_request_id(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection())

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers={
            **AUTH,
            "X-Orvo-Role": "viewer",
            "X-Orvo-Businesses": "other",
            "X-Request-ID": "req-denied token=raw_denied_request_id_secret",
        },
    )

    assert response.status_code == 403
    raw_body = response.get_data(as_text=True)
    assert "raw_denied_request_id_secret" not in raw_body
    body = response.get_json()
    assert body["request_id"] == "[REDACTED]"
    assert body["redaction_applied"] is True
    events = _audit_events(db_path)
    assert len(events) == 1
    event = events[0]
    assert event["request_id"] == "[REDACTED]"
    assert "raw_denied_request_id_secret" not in json.dumps(event, sort_keys=True)


def test_internal_error_envelope_and_audit_reject_oversized_request_id(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection())
    oversized_request_id = "req-" + "a" * 256

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers={
            **AUTH,
            "X-Orvo-Role": "viewer",
            "X-Orvo-Businesses": "other",
            "X-Request-ID": oversized_request_id,
        },
    )

    assert response.status_code == 403
    raw_body = response.get_data(as_text=True)
    assert oversized_request_id not in raw_body
    body = response.get_json()
    assert body["request_id"] == "[REDACTED]"
    assert body["redaction_applied"] is True
    events = _audit_events(db_path)
    assert len(events) == 1
    event = events[0]
    assert event["request_id"] == "[REDACTED]"
    assert oversized_request_id not in json.dumps(event, sort_keys=True)


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


def test_internal_case_queue_enforces_gateway_policy_before_store_access(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)
    evaluated_contexts = []

    class DenyingGatewayRegistry:
        def evaluate(self, context):
            evaluated_contexts.append(context)
            return SimpleNamespace(
                allowed=False,
                code="gateway_test_denied",
                reason="Gateway test denial.",
                status_code=429,
            )

    import app.http.internal_brain.common as internal_common

    monkeypatch.setattr(internal_common, "default_gateway_policy_registry", lambda: DenyingGatewayRegistry())

    response = client.get("/internal/brain/businesses/artemea/cases?status=open", headers=AUTH)

    assert response.status_code == 429
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "gateway_test_denied"
    assert len(evaluated_contexts) == 1
    context = evaluated_contexts[0]
    assert context.route_key == "operator_api.case_queue.read"
    assert context.method == "GET"
    assert context.business_id == "artemea"
    assert context.principal.actor_id == "operator:juan"


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
        headers={**AUTH, "X-Idempotency-Key": "case-action:artemea:cross-business"},
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


def test_internal_case_action_requires_gateway_idempotency_key_before_mutation(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())
    headers = {key: value for key, value in AUTH.items() if key != "X-Idempotency-Key"}

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={**headers, "X-Request-ID": "req-missing-idempotency"},
        json={
            "action_key": "acknowledge_case",
            "metadata": {"access_token": "raw_idempotency_secret"},
        },
    )

    assert response.status_code == 428
    raw_body = response.get_data(as_text=True)
    assert "raw_idempotency_secret" not in raw_body
    body = response.get_json()
    assert body["ok"] is False
    assert body["business_id"] == "artemea"
    assert body["error"]["code"] == "missing_idempotency_key"
    assert body["redaction_applied"] is True

    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.status == "open"
    assert len(reloaded.timeline) == len(case.timeline)

    events = _audit_events(db_path)
    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "operator.case_action.denied"
    assert event["target_id"] == case.case_id
    assert event["request_id"] == "req-missing-idempotency"
    assert event["data"]["gateway_policy"]["route_key"] == "operator_api.case_action.mutate"
    assert event["data"]["gateway_policy"]["decision_code"] == "missing_idempotency_key"
    assert event["data"]["gateway_policy"]["idempotency_key_present"] is False
    assert "raw_idempotency_secret" not in json.dumps(event, sort_keys=True)


def test_internal_case_action_accepts_standard_idempotency_key_header(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())
    headers = {key: value for key, value in AUTH.items() if key != "X-Idempotency-Key"}

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={
            **headers,
            "Idempotency-Key": "case-action:artemea:standard-header",
            "X-Request-ID": "req-standard-idempotency-key",
        },
        json={"action_key": "acknowledge_case", "reason": "Using the standard header"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["data"]["case"]["status"] == "acknowledged"
    assert body["data"]["action"]["idempotency_key"] == "case-action:artemea:standard-header"
    assert body["data"]["action"]["status"] == "executed"

    replay = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={
            **headers,
            "Idempotency-Key": "case-action:artemea:standard-header",
            "X-Request-ID": "req-standard-idempotency-key-replay",
        },
        json={"action_key": "acknowledge_case", "reason": "Using the standard header"},
    )

    assert replay.status_code == 200
    assert replay.get_json()["data"]["action"]["status"] == "skipped_duplicate"


def test_internal_case_action_rejects_non_object_payload_without_mutation(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={**AUTH, "X-Request-ID": "req-non-object-payload"},
        json=["acknowledge_case", {"api_key": "raw_payload_secret"}],
    )

    assert response.status_code == 400
    raw_body = response.get_data(as_text=True)
    assert "raw_payload_secret" not in raw_body
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_case_action_payload"
    assert body["redaction_applied"] is True

    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.status == "open"
    assert len(reloaded.timeline) == len(case.timeline)

    events = _audit_events(db_path)
    matching_events = [event for event in events if event["request_id"] == "req-non-object-payload"]
    assert len(matching_events) == 1
    event = matching_events[0]
    assert event["event_type"] == "operator.case_action.failed"
    assert event["data"]["error_code"] == "invalid_case_action_payload"
    assert "raw_payload_secret" not in json.dumps(event, sort_keys=True)

def test_internal_case_action_rejects_unknown_key_without_mutation(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={**AUTH, "X-Idempotency-Key": "case-action:artemea:unknown-key"},
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


def test_internal_case_action_rejects_registered_external_action_at_operator_api_boundary_without_mutation(
    monkeypatch,
    tmp_path,
):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())
    external_action_calls = []

    import app.brain.external_actions as external_actions

    def _forbidden_external_action_call(*args, **kwargs):
        external_action_calls.append((args, kwargs))
        raise AssertionError("operator API must not call the external action provider boundary")

    monkeypatch.setattr(external_actions, "execute_external_action", _forbidden_external_action_call)

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={
            **AUTH,
            "X-Idempotency-Key": "case-action:artemea:external-boundary",
            "X-Request-ID": "req-external-boundary",
        },
        json={
            "action_key": "request_external_action",
            "reason": "Create CRM ticket access_token=raw_external_boundary_secret",
            "metadata": {
                "provider": "pipedream",
                "toolkit": "hubspot",
                "external_action_key": "hubspot.create_ticket",
                "api_key": "raw_external_boundary_secret",
            },
        },
    )

    assert response.status_code == 400
    raw_body = response.get_data(as_text=True)
    assert "raw_external_boundary_secret" not in raw_body
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "case_action_api_disabled"
    assert body["redaction_applied"] is True
    assert external_action_calls == []

    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.status == "open"
    assert len(reloaded.timeline) == len(case.timeline)

    events = _audit_events(db_path)
    matching_events = [event for event in events if event["request_id"] == "req-external-boundary"]
    assert len(matching_events) == 1
    event = matching_events[0]
    assert event["event_type"] == "operator.case_action.failed"
    assert event["data"]["action_key"] == "request_external_action"
    assert event["data"]["error_code"] == "case_action_api_disabled"
    assert event["data"]["payload"]["metadata"]["api_key"] == "[REDACTED]"
    assert "raw_external_boundary_secret" not in json.dumps(event, sort_keys=True)


def test_internal_operator_api_does_not_import_external_action_execution_boundary():
    repo_root = Path(__file__).resolve().parents[1]
    checked_paths = [
        *sorted((repo_root / "app" / "brain" / "operator_api").glob("*.py")),
        *sorted((repo_root / "app" / "http" / "internal_brain").glob("*.py")),
    ]
    forbidden_imports = {}
    for path in checked_paths:
        source = path.read_text(encoding="utf-8")
        forbidden_tokens = [
            token
            for token in ("app.brain.external_actions", "execute_external_action")
            if token in source
        ]
        if forbidden_tokens:
            forbidden_imports[str(path.relative_to(repo_root))] = forbidden_tokens

    assert forbidden_imports == {}


def test_internal_case_action_actor_identity_comes_from_authenticated_header(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())
    headers = {
        **AUTH,
        "X-Orvo-Operator": "operator:trusted",
        "X-Idempotency-Key": "case-action:artemea:actor-identity",
    }

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


def test_internal_case_action_collapses_secret_shaped_authenticated_actor_before_persistence(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={
            **AUTH,
            "X-Orvo-Operator": "operator:juan access_token=raw_action_actor_secret",
            "X-Idempotency-Key": "case-action-redacted-actor",
        },
        json={"action_key": "add_comment", "comment": "Revisado por operaciones"},
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_action_actor_secret" not in raw_body
    body = response.get_json()
    latest_event = body["data"]["case"]["timeline"][-1]
    assert latest_event["event_type"] == "operator_comment"
    assert latest_event["actor_ref"] == "[REDACTED]"

    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.timeline[-1].actor_ref == "[REDACTED]"
    assert "raw_action_actor_secret" not in reloaded.model_dump_json()


def test_internal_case_actions_acknowledge_and_resolve_with_actor_and_redaction(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    ack = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={**AUTH, "X-Idempotency-Key": "case-action:artemea:ack-redaction"},
        json={"action_key": "acknowledge_case", "reason": "Estoy encima"},
    )
    assert ack.status_code == 200
    assert ack.get_json()["data"]["case"]["status"] == "acknowledged"

    resolved = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={**AUTH, "X-Idempotency-Key": "case-action:artemea:resolve"},
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


def test_internal_case_action_idempotency_key_skips_duplicate_mutation_durably(monkeypatch, tmp_path):
    from app.brain.workflow_action_ledger import SQLiteWorkflowActionLedgerStore

    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())
    headers = {**AUTH, "X-Idempotency-Key": "case-action:artemea:ack-1"}

    first = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers=headers,
        json={"action_key": "acknowledge_case", "reason": "Estoy encima"},
    )

    assert first.status_code == 200
    first_body = first.get_json()
    assert first_body["data"]["case"]["status"] == "acknowledged"
    assert first_body["data"]["action"]["status"] == "executed"
    assert first_body["data"]["action"]["idempotency_key"] == "case-action:artemea:ack-1"
    assert first_body["data"]["action"]["execution_state"] == "executed"
    timeline_count_after_first = len(first_body["data"]["case"]["timeline"])

    duplicate = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers=headers,
        json={"action_key": "acknowledge_case", "reason": "Duplicate retry should not add timeline"},
    )

    assert duplicate.status_code == 200
    duplicate_body = duplicate.get_json()
    assert duplicate_body["data"]["case"]["status"] == "acknowledged"
    assert duplicate_body["data"]["action"]["status"] == "skipped_duplicate"
    assert duplicate_body["data"]["action"]["idempotency_key"] == "case-action:artemea:ack-1"
    assert duplicate_body["data"]["action"]["execution_state"] == "executed"
    assert len(duplicate_body["data"]["case"]["timeline"]) == timeline_count_after_first

    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.status == "acknowledged"
    assert len(reloaded.timeline) == timeline_count_after_first

    actions = SQLiteWorkflowActionLedgerStore(str(db_path)).list_actions(business_id="artemea")
    assert len(actions) == 1
    [record] = actions
    assert record.source == "manual_operator"
    assert record.action_key == "acknowledge_case"
    assert record.case_id == case.case_id
    assert record.idempotency_key == "case-action:artemea:ack-1"
    assert record.execution_state == "executed"
    assert record.approval_state == "not_required"
    assert record.params["reason"] == "Estoy encima"


def test_internal_case_action_existing_pending_idempotency_key_blocks_duplicate_side_effect(
    monkeypatch,
    tmp_path,
):
    from app.brain.workflow_action_ledger import SQLiteWorkflowActionLedgerStore

    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())
    ledger = SQLiteWorkflowActionLedgerStore(str(db_path))
    ledger.record_planned_action(
        business_id="artemea",
        case_id=case.case_id,
        action_key="acknowledge_case",
        idempotency_key="case-action:artemea:pending-1",
        execution_state="pending_execution",
        approval_required=False,
        source="manual_operator",
        actor_ref="operator:juan",
        params={"reason": "already accepted before side effect"},
    )

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={**AUTH, "X-Idempotency-Key": "case-action:artemea:pending-1"},
        json={"action_key": "acknowledge_case", "reason": "retry while first attempt is pending"},
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "idempotency_key_in_progress"

    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.status == "open"
    assert len(reloaded.timeline) == len(case.timeline)


def test_internal_case_action_failed_validation_does_not_consume_idempotency_key(monkeypatch, tmp_path):
    from app.brain.workflow_action_ledger import SQLiteWorkflowActionLedgerStore

    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())
    headers = {**AUTH, "X-Idempotency-Key": "case-action:artemea:retry-after-validation"}

    invalid = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers=headers,
        json={"action_key": "resolve_case"},
    )

    assert invalid.status_code == 400
    assert invalid.get_json()["error"]["code"] == "missing_case_action_reason"
    assert SQLiteWorkflowActionLedgerStore(str(db_path)).list_actions(business_id="artemea") == []

    retry = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers=headers,
        json={"action_key": "acknowledge_case", "reason": "valid retry"},
    )

    assert retry.status_code == 200
    retry_body = retry.get_json()
    assert retry_body["data"]["case"]["status"] == "acknowledged"
    assert retry_body["data"]["action"]["status"] == "executed"
    assert retry_body["data"]["action"]["idempotency_key"] == "case-action:artemea:retry-after-validation"


def test_internal_case_action_secret_shaped_idempotency_key_is_rejected_without_ledger_or_mutation(
    monkeypatch,
    tmp_path,
):
    from app.brain.workflow_action_ledger import SQLiteWorkflowActionLedgerStore

    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())
    secret_idempotency_key = "case-action/access_token:raw_idempotency_secret"

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={
            **AUTH,
            "X-Idempotency-Key": secret_idempotency_key,
            "X-Request-ID": "req-secret-idempotency-key",
        },
        json={"action_key": "acknowledge_case", "reason": "valid mutation must not run"},
    )

    assert response.status_code == 400
    raw_body = response.get_data(as_text=True)
    assert "raw_idempotency_secret" not in raw_body
    body = response.get_json()
    assert body["error"]["code"] == "invalid_idempotency_key"
    assert body["redaction_applied"] is True
    assert SQLiteWorkflowActionLedgerStore(str(db_path)).list_actions(business_id="artemea") == []

    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.status == "open"
    assert len(reloaded.timeline) == len(case.timeline)

    matching_events = [
        event for event in _audit_events(db_path) if event["request_id"] == "req-secret-idempotency-key"
    ]
    assert len(matching_events) == 1
    event_json = json.dumps(matching_events[0], sort_keys=True)
    assert "raw_idempotency_secret" not in event_json
    assert secret_idempotency_key not in event_json


def test_internal_case_action_requires_idempotency_key_before_mutation(monkeypatch, tmp_path):
    from app.brain.workflow_action_ledger import SQLiteWorkflowActionLedgerStore

    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    headers = {key: value for key, value in AUTH.items() if key != "X-Idempotency-Key"}
    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={**headers, "X-Request-ID": "req-missing-idempotency-key"},
        json={"action_key": "acknowledge_case", "reason": "should require replay safety"},
    )

    assert response.status_code == 428
    body = response.get_json()
    assert body["error"]["code"] == "missing_idempotency_key"
    assert SQLiteWorkflowActionLedgerStore(str(db_path)).list_actions(business_id="artemea") == []

    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.status == "open"
    assert len(reloaded.timeline) == len(case.timeline)

    matching_events = [
        event for event in _audit_events(db_path) if event["request_id"] == "req-missing-idempotency-key"
    ]
    assert len(matching_events) == 1
    event = matching_events[0]
    assert event["event_type"] == "operator.case_action.denied"
    assert event["data"]["gateway_policy"]["decision_code"] == "missing_idempotency_key"
    assert event["data"]["status_code"] == 428


def test_internal_case_action_assign_owner_uses_owner_ref_alias_and_redacts(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={**AUTH, "X-Idempotency-Key": "case-action:artemea:assign-owner"},
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


def test_internal_success_envelope_redacts_secret_shaped_business_id(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea%20access_token=raw_business_secret/operator-session",
        headers=AUTH,
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_business_secret" not in raw_body
    body = response.get_json()
    assert body["business_id"] == "[REDACTED]"
    assert body["redaction_applied"] is True


def test_internal_error_envelope_redacts_secret_shaped_business_id_before_auth(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea%20access_token=raw_business_secret/operator-session",
    )

    assert response.status_code == 401
    raw_body = response.get_data(as_text=True)
    assert "raw_business_secret" not in raw_body
    body = response.get_json()
    assert body["business_id"] == "[REDACTED]"
    assert body["redaction_applied"] is True


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
            "can_execute_runtime": False,
            "can_read_operator_audit": False,
        },
        "business_scope": {
            "legacy_token_scoped": True,
            "all_businesses": False,
            "allowed_businesses": None,
        },
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
    assert operator["can_execute_runtime"] is False
    assert operator["can_read_operator_audit"] is False


def test_internal_operator_session_projects_admin_audit_permission(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/operator-session",
        headers={**AUTH, "X-Orvo-Role": "admin", "X-Orvo-Operator": "admin:sol"},
    )

    assert response.status_code == 200
    operator = response.get_json()["data"]["operator"]
    assert operator["role"] == "admin"
    assert operator["permissions"] == ["case:action", "internal:read", "operator_audit:read", "runtime:execute"]
    assert operator["can_read_internal"] is True
    assert operator["can_mutate_cases"] is True
    assert operator["can_execute_runtime"] is True
    assert operator["can_read_operator_audit"] is True


def test_internal_operator_session_projects_redacted_business_grants(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/operator-session",
        headers={
            **AUTH,
            "X-Orvo-Businesses": "artemea, other access_token=raw_scope_secret",
        },
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_scope_secret" not in raw_body
    body = response.get_json()
    assert body["data"]["business_scope"] == {
        "legacy_token_scoped": False,
        "all_businesses": False,
        "allowed_businesses": ["artemea", "[REDACTED]"],
    }
    assert body["redaction_applied"] is True


def test_internal_read_allows_viewer_role(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.get(f"/internal/brain/businesses/artemea/cases/{case.case_id}", headers=VIEWER_AUTH)

    assert response.status_code == 200
    assert response.get_json()["data"]["case"]["case_id"] == case.case_id


def test_internal_read_allows_matching_operator_business_grant(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.get(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}",
        headers={**AUTH, "X-Orvo-Businesses": "other, artemea"},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["case"]["case_id"] == case.case_id


def test_internal_read_denies_mismatched_operator_business_grant_and_audits(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.get(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}",
        headers={
            **AUTH,
            "X-Orvo-Businesses": "other, demo-secret access_token=raw_grant_secret",
            "X-Request-ID": "req-business-denied",
        },
    )

    assert response.status_code == 403
    raw_body = response.get_data(as_text=True)
    assert "raw_grant_secret" not in raw_body
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "forbidden"
    assert body["redaction_applied"] is True
    events = _audit_events(db_path)
    assert len(events) == 1
    event = events[0]
    assert event["business_id"] == "artemea"
    assert event["actor_ref"] == "operator:juan"
    assert event["event_type"] == "operator.authorization.denied"
    assert event["target_type"] == "internal_operator_api"
    assert event["target_id"] == "artemea"
    assert event["request_id"] == "req-business-denied"
    assert event["data"]["reason"] == "business_scope_denied"
    assert event["data"]["permission"] == "business:access"
    assert event["data"]["allowed_businesses"] == ["other", "[REDACTED]"]
    assert "raw_grant_secret" not in json.dumps(event, sort_keys=True)


def test_internal_case_action_rejects_viewer_role_without_mutation(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={
            **VIEWER_AUTH,
            "X-Orvo-Operator": "viewer:ana access_token=raw_viewer_actor_secret",
            "X-Request-ID": "req-viewer-action-denied",
        },
        json={
            "action_key": "acknowledge_case",
            "reason": "Intento viewer api_key=raw_viewer_payload_secret",
        },
    )

    assert response.status_code == 403
    raw_body = response.get_data(as_text=True)
    assert "raw_viewer_actor_secret" not in raw_body
    assert "raw_viewer_payload_secret" not in raw_body
    body = response.get_json()
    assert body["error"]["code"] == "forbidden"
    assert body["redaction_applied"] is True
    conn = sqlite3.connect(db_path)
    reloaded = SQLiteOperationalCaseStore(conn).get_case(case.case_id)
    conn.close()
    assert reloaded is not None
    assert reloaded.status == "open"
    assert len(reloaded.timeline) == len(case.timeline)

    events = _audit_events(db_path)
    matching_events = [event for event in events if event["request_id"] == "req-viewer-action-denied"]
    assert len(matching_events) == 1
    event = matching_events[0]
    assert event["business_id"] == "artemea"
    assert event["actor_ref"] == "[REDACTED]"
    assert event["event_type"] == "operator.case_action.denied"
    assert event["target_type"] == "operational_case"
    assert event["target_id"] == case.case_id
    assert event["data"]["action_key"] == "acknowledge_case"
    assert event["data"]["permission"] == "case:action"
    assert event["data"]["status_code"] == 403
    assert event["data"]["payload"]["reason"] == "Intento viewer api_key=[REDACTED]"
    assert "raw_viewer_actor_secret" not in json.dumps(event, sort_keys=True)
    assert "raw_viewer_payload_secret" not in json.dumps(event, sort_keys=True)


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


def test_internal_read_unknown_role_audit_redacts_malformed_role_header(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())

    response = client.get(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}",
        headers={
            **AUTH,
            "X-Orvo-Role": "superuser access_token=raw_role_secret",
            "X-Orvo-Operator": "operator:juan",
            "X-Request-ID": "req-unknown-role",
        },
    )

    assert response.status_code == 403
    raw_body = response.get_data(as_text=True)
    assert "raw_role_secret" not in raw_body
    events = _audit_events(db_path)
    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "operator.authorization.denied"
    assert event["request_id"] == "req-unknown-role"
    assert event["data"]["reason"] == "unknown_operator_role"
    assert event["data"]["role"] == "[REDACTED]"
    assert "raw_role_secret" not in json.dumps(event, sort_keys=True)


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


def test_internal_case_queue_summary_by_severity_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-artemea-critical", severity="critical"))
    _seed_case(
        db_path,
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            priority=70,
            severity="warning",
            title="Ventas bajaron",
            run_id="run-artemea-warning",
            freshness_state="stale",
        ),
    )
    _seed_case(
        db_path,
        _case_detection(
            business_id="other",
            run_id="run-other-critical",
            severity="critical",
        ),
    )

    response = client.get(
        "/internal/brain/businesses/artemea/cases/summary/by-severity",
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
    assert summary["totals_by_severity"] == {"critical": 1, "warning": 1}
    assert summary["actionable_by_severity"] == {"critical": 1, "warning": 1}
    assert summary["actionable_degraded_by_severity"] == {"warning": 1}


def test_internal_case_queue_summary_by_severity_excludes_terminal_stale_cases_from_actionable_counts(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection(run_id="run-artemea-critical", severity="critical"))
    terminal_stale = _seed_case(
        db_path,
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            priority=70,
            severity="warning",
            title="Ventas bajaron",
            run_id="run-artemea-terminal-stale",
            freshness_state="stale",
        ),
    )

    with sqlite3.connect(db_path) as conn:
        init_schema(conn)
        store = SQLiteOperationalCaseStore(conn)
        store.transition_case(
            terminal_stale.case_id,
            status="acknowledged",
            actor_type="operator",
            actor_ref="operator:juan",
            transitioned_at=_utc(9),
        )
        store.transition_case(
            terminal_stale.case_id,
            status="resolved",
            actor_type="operator",
            actor_ref="operator:juan",
            reason="Resolved stale warning before summary",
            transitioned_at=_utc(10),
        )

    response = client.get(
        "/internal/brain/businesses/artemea/cases/summary/by-severity",
        headers=AUTH,
    )

    assert response.status_code == 200
    summary = response.get_json()["data"]
    assert summary["total"] == 2
    assert summary["totals_by_severity"] == {"critical": 1, "warning": 1}
    assert summary["actionable_total"] == 1
    assert summary["actionable_by_severity"] == {"critical": 1}
    assert summary["actionable_degraded_by_severity"] == {}


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


def test_internal_case_queue_aging_by_source_connector_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.upsert_detection(
        _case_detection(
            run_id="run-artemea-tn-aging",
            source="tiendanube",
            source_label="Tiendanube access_token=raw_source_secret",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    store.upsert_detection(
        _case_detection(
            run_id="run-artemea-sheets-aging",
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            source="google_sheets",
            source_label="Google Sheets access_token=raw_source_secret",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-tn-aging",
            source="tiendanube",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/aging/by-source-connector",
        headers=AUTH,
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "raw_source_secret" not in raw_body
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["actionable_total"] == 2
    assert data["by_age_bucket"]["under_6h"] == 2
    assert data["by_age_bucket_source_connector"]["under_6h"] == {
        "tiendanube": 1,
        "google_sheets": 1,
    }
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


def test_internal_case_queue_stagnation_by_case_type_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.upsert_detection(
        _case_detection(run_id="run-artemea-stockout-stalled"),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            priority=70,
            severity="warning",
            title="Ventas en baja",
            run_id="run-artemea-sales-stalled",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    store.upsert_detection(
        _case_detection(
            business_id="other",
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            priority=70,
            severity="warning",
            title="Ventas en baja",
            run_id="run-other-sales-stalled",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/stagnation/by-case-type",
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
    assert data["by_idle_bucket"]["under_6h"] == 2
    assert data["by_idle_bucket_case_type"]["under_6h"] == {"stockout_risk": 1, "sales_drop": 1}
    assert data["most_stalled_actionable"]["case_type"] in {"stockout_risk", "sales_drop"}


def test_internal_case_queue_stagnation_by_severity_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    store.upsert_detection(
        _case_detection(run_id="run-artemea-critical", severity="critical"),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            priority=70,
            severity="warning",
            title="Ventas en baja",
            run_id="run-artemea-warning",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-critical",
            severity="critical",
        ),
        detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/stagnation/by-severity",
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
    assert data["by_idle_bucket"]["under_6h"] == 2
    assert data["by_idle_bucket_severity"]["under_6h"] == {"critical": 1, "warning": 1}
    assert data["most_stalled_actionable"]["case_type"] in {"stockout_risk", "sales_drop"}


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


def test_internal_workflow_throughput_by_entity_kind_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    product = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-product-throughput",
            dedupe_suffix="stockout_risk/product/sku-product-throughput/commerce.inventory/daily",
            entity_scope={"kind": "product", "id": "sku-product", "label": "SKU Product"},
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        product.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        product.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=3),
    )
    channel = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-channel-throughput",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            entity_scope={"kind": "channel", "id": "all", "label": "Todos"},
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        channel.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=2),
    )
    store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-product-throughput",
            dedupe_suffix="stockout_risk/product/sku-other-throughput/commerce.inventory/daily",
            entity_scope={"kind": "product", "id": "sku-other", "label": "SKU Other"},
        ),
        detected_at=opened_at,
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/workflow/throughput/by-entity-kind",
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
    assert data["totals_by_entity_kind"] == {"product": 1, "channel": 1}
    assert data["acknowledged_by_entity_kind"] == {"product": 1, "channel": 1}
    assert data["resolved_by_entity_kind"] == {"product": 1}
    assert data["time_to_acknowledge_seconds_by_entity_kind"] == {
        "product": {"min": 3600, "max": 3600, "avg": 3600, "median": 3600},
        "channel": {"min": 7200, "max": 7200, "avg": 7200, "median": 7200},
    }
    assert data["time_to_resolve_seconds_by_entity_kind"] == {
        "product": {"min": 10800, "max": 10800, "avg": 10800, "median": 10800}
    }


def test_internal_case_acknowledgment_latency_histogram_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    fast = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-fast-ack",
            severity="critical",
            dedupe_suffix="stockout_risk/product/sku-fast-ack/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        fast.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(minutes=30),
    )
    slow = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-slow-ack",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        slow.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=8),
    )
    unacknowledged = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-unacknowledged",
            dedupe_suffix="stockout_risk/product/sku-unacknowledged/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    other = store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-slow-ack",
            dedupe_suffix="stockout_risk/product/sku-other-ack/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/acknowledgment-latency",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["acknowledged_total"] == 2
    assert data["by_acknowledgment_bucket"] == {
        "under_1h": 1,
        "under_6h": 0,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_acknowledgment_bucket_severity"]["under_1h"] == {"critical": 1}
    assert data["by_acknowledgment_bucket_severity"]["under_24h"] == {"warning": 1}
    assert data["fastest_acknowledged"]["case_id"] == fast.case_id
    assert data["fastest_acknowledged"]["time_to_acknowledge_seconds"] == 1800
    assert data["slowest_acknowledged"]["case_id"] == slow.case_id
    assert data["slowest_acknowledged"]["time_to_acknowledge_seconds"] == 28800
    assert unacknowledged.case_id not in {
        data["fastest_acknowledged"]["case_id"],
        data["slowest_acknowledged"]["case_id"],
    }


def test_internal_case_acknowledgment_latency_by_case_type_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    stockout = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-fast-ack-case-type",
            case_type="stockout_risk",
            severity="critical",
            dedupe_suffix="stockout_risk/product/sku-fast-ack-case-type/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        stockout.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(minutes=30),
    )
    sales = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-slow-ack-case-type",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        sales.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=8),
    )
    other = store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-ack-case-type",
            dedupe_suffix="stockout_risk/product/sku-other-ack-case-type/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/acknowledgment-latency/by-case-type",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["acknowledged_total"] == 2
    assert data["by_acknowledgment_bucket"] == {
        "under_1h": 1,
        "under_6h": 0,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_acknowledgment_bucket_case_type"] == {
        "under_1h": {"stockout_risk": 1},
        "under_6h": {},
        "under_24h": {"sales_drop": 1},
        "under_7d": {},
        "over_7d": {},
    }
    assert data["fastest_acknowledged"]["case_id"] == stockout.case_id
    assert data["fastest_acknowledged"]["case_type"] == "stockout_risk"
    assert data["slowest_acknowledged"]["case_id"] == sales.case_id
    assert data["slowest_acknowledged"]["case_type"] == "sales_drop"


def test_internal_case_acknowledgment_latency_by_entity_kind_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    product = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-product-ack-entity-kind",
            case_type="stockout_risk",
            severity="critical",
            dedupe_suffix="stockout_risk/product/sku-product-ack-entity-kind/commerce.inventory/daily",
            entity_scope={"kind": "product", "id": "sku-product", "label": "SKU Product"},
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        product.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(minutes=30),
    )
    channel = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-channel-ack-entity-kind",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
            entity_scope={"kind": "channel", "id": "all", "label": "Todos"},
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        channel.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=8),
    )
    other = store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-ack-entity-kind",
            dedupe_suffix="stockout_risk/product/sku-other-ack-entity-kind/commerce.inventory/daily",
            entity_scope={"kind": "product", "id": "sku-other", "label": "SKU Other"},
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/acknowledgment-latency/by-entity-kind",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["acknowledged_total"] == 2
    assert data["by_acknowledgment_bucket"] == {
        "under_1h": 1,
        "under_6h": 0,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_acknowledgment_bucket_entity_kind"] == {
        "under_1h": {"product": 1},
        "under_6h": {},
        "under_24h": {"channel": 1},
        "under_7d": {},
        "over_7d": {},
    }
    assert data["fastest_acknowledged"]["case_id"] == product.case_id
    assert data["fastest_acknowledged"]["case_type"] == "stockout_risk"
    assert data["slowest_acknowledged"]["case_id"] == channel.case_id
    assert data["slowest_acknowledged"]["case_type"] == "sales_drop"


def test_internal_case_acknowledgment_latency_by_source_connector_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    tiendanube = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-tiendanube-ack-source",
            source="tiendanube",
            source_label="Tiendanube",
            dedupe_suffix="stockout_risk/product/sku-tiendanube-ack-source/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        tiendanube.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(minutes=30),
    )
    csv = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-csv-ack-source",
            source="csv",
            source_label="CSV import",
            dedupe_suffix="sales_drop/channel/csv/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        csv.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=8),
    )
    other_tenant = store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-ack-source",
            source="meta_ads",
            source_label="Meta Ads",
            dedupe_suffix="stockout_risk/product/sku-other-ack-source/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other_tenant.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/acknowledgment-latency/by-source-connector",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["acknowledged_total"] == 2
    assert data["by_acknowledgment_bucket"] == {
        "under_1h": 1,
        "under_6h": 0,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_acknowledgment_bucket_source_connector"] == {
        "under_1h": {"tiendanube": 1},
        "under_6h": {},
        "under_24h": {"csv": 1},
        "under_7d": {},
        "over_7d": {},
    }
    assert data["fastest_acknowledged"]["case_id"] == tiendanube.case_id
    assert data["slowest_acknowledged"]["case_id"] == csv.case_id
    assert "meta_ads" not in str(data)


def test_internal_case_acknowledgment_latency_by_priority_bracket_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    high = store.upsert_detection(
        _case_detection(
            priority=95,
            run_id="run-artemea-high-ack",
            dedupe_suffix="stockout_risk/product/sku-high-ack/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        high.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(minutes=30),
    )
    medium = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-medium-ack",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        medium.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=8),
    )
    low_other_tenant = store.upsert_detection(
        _case_detection(
            business_id="other",
            priority=20,
            run_id="run-other-low-ack",
            dedupe_suffix="stockout_risk/product/sku-low-ack/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        low_other_tenant.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/acknowledgment-latency/by-priority-bracket",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["acknowledged_total"] == 2
    assert data["by_acknowledgment_bucket"] == {
        "under_1h": 1,
        "under_6h": 0,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_acknowledgment_bucket_priority_bracket"]["under_1h"] == {"high": 1}
    assert data["by_acknowledgment_bucket_priority_bracket"]["under_24h"] == {"medium": 1}
    assert data["by_acknowledgment_bucket_priority_bracket"]["over_7d"] == {}
    assert data["fastest_acknowledged"]["case_id"] == high.case_id
    assert data["slowest_acknowledged"]["case_id"] == medium.case_id


def test_internal_case_resolution_latency_histogram_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    fast = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-fast-resolved",
            severity="critical",
            dedupe_suffix="stockout_risk/product/sku-fast-resolved/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        fast.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        fast.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=3),
    )
    slow = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-slow-resolved",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        slow.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        slow.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=10),
    )
    unresolved = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-unresolved",
            dedupe_suffix="stockout_risk/product/sku-unresolved/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    other = store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-resolved",
            dedupe_suffix="stockout_risk/product/sku-other-resolved/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        other.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/resolution-latency",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["resolved_total"] == 2
    assert data["by_resolution_bucket"] == {
        "under_1h": 0,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_resolution_bucket_severity"]["under_6h"] == {"critical": 1}
    assert data["by_resolution_bucket_severity"]["under_24h"] == {"warning": 1}
    assert data["fastest_resolved"]["case_id"] == fast.case_id
    assert data["fastest_resolved"]["time_to_resolve_seconds"] == 10800
    assert data["slowest_resolved"]["case_id"] == slow.case_id
    assert data["slowest_resolved"]["time_to_resolve_seconds"] == 36000
    assert unresolved.case_id not in {
        data["fastest_resolved"]["case_id"],
        data["slowest_resolved"]["case_id"],
    }


def test_internal_case_resolution_latency_by_case_type_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    stockout = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-fast-resolved-case-type",
            case_type="stockout_risk",
            severity="critical",
            dedupe_suffix="stockout_risk/product/sku-fast-resolved-case-type/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        stockout.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        stockout.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=3),
    )
    sales = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-slow-resolved-case-type",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        sales.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        sales.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=10),
    )
    other = store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-resolved-case-type",
            dedupe_suffix="stockout_risk/product/sku-other-resolved-case-type/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        other.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/resolution-latency/by-case-type",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["resolved_total"] == 2
    assert data["by_resolution_bucket"] == {
        "under_1h": 0,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_resolution_bucket_case_type"] == {
        "under_1h": {},
        "under_6h": {"stockout_risk": 1},
        "under_24h": {"sales_drop": 1},
        "under_7d": {},
        "over_7d": {},
    }
    assert data["fastest_resolved"]["case_id"] == stockout.case_id
    assert data["fastest_resolved"]["case_type"] == "stockout_risk"
    assert data["slowest_resolved"]["case_id"] == sales.case_id
    assert data["slowest_resolved"]["case_type"] == "sales_drop"


def test_internal_case_resolution_latency_by_source_connector_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    tiendanube = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-tiendanube-resolved-source",
            source="tiendanube",
            source_label="Tiendanube",
            dedupe_suffix="stockout_risk/product/sku-tiendanube-resolved-source/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        tiendanube.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        tiendanube.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=3),
    )
    csv = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-csv-resolved-source",
            source="csv",
            source_label="CSV import",
            dedupe_suffix="sales_drop/channel/csv/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        csv.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        csv.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=10),
    )
    other_tenant = store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-resolved-source",
            source="meta_ads",
            source_label="Meta Ads",
            dedupe_suffix="stockout_risk/product/sku-other-resolved-source/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other_tenant.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        other_tenant.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/resolution-latency/by-source-connector",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["resolved_total"] == 2
    assert data["by_resolution_bucket"] == {
        "under_1h": 0,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_resolution_bucket_source_connector"] == {
        "under_1h": {},
        "under_6h": {"tiendanube": 1},
        "under_24h": {"csv": 1},
        "under_7d": {},
        "over_7d": {},
    }
    assert data["fastest_resolved"]["case_id"] == tiendanube.case_id
    assert data["slowest_resolved"]["case_id"] == csv.case_id
    assert "meta_ads" not in str(data)


def test_internal_case_resolution_latency_by_priority_bracket_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    high = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-high-resolved-priority",
            priority=95,
            dedupe_suffix="stockout_risk/product/sku-high-resolved-priority/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        high.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        high.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=3),
    )
    medium = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-medium-resolved-priority",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        medium.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        medium.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=10),
    )
    other = store.upsert_detection(
        _case_detection(
            business_id="other",
            priority=20,
            run_id="run-other-resolved-priority",
            dedupe_suffix="data_stale/business/monitored/observability.feeds/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        other.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/resolution-latency/by-priority-bracket",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["resolved_total"] == 2
    assert data["by_resolution_bucket"] == {
        "under_1h": 0,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_resolution_bucket_priority_bracket"] == {
        "under_1h": {},
        "under_6h": {"high": 1},
        "under_24h": {"medium": 1},
        "under_7d": {},
        "over_7d": {},
    }
    assert data["fastest_resolved"]["case_id"] == high.case_id
    assert data["slowest_resolved"]["case_id"] == medium.case_id


def test_internal_case_handling_latency_histogram_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    fast = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-fast-handled",
            severity="critical",
            dedupe_suffix="stockout_risk/product/sku-fast-handled/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        fast.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        fast.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=3),
    )
    slow = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-slow-handled",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        slow.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        slow.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=10),
    )
    unhandled = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-unhandled",
            dedupe_suffix="stockout_risk/product/sku-unhandled/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        unhandled.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    other = store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-handled",
            dedupe_suffix="stockout_risk/product/sku-other-handled/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        other.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/handling-latency",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["handled_total"] == 2
    assert data["by_handling_bucket"] == {
        "under_1h": 0,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_handling_bucket_severity"]["under_6h"] == {"critical": 1}
    assert data["by_handling_bucket_severity"]["under_24h"] == {"warning": 1}
    assert data["fastest_handled"]["case_id"] == fast.case_id
    assert data["fastest_handled"]["time_to_handle_seconds"] == 7200
    assert data["slowest_handled"]["case_id"] == slow.case_id
    assert data["slowest_handled"]["time_to_handle_seconds"] == 32400


def test_internal_handling_latency_by_severity_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    handled = store.upsert_detection(
        _case_detection(
            severity="critical",
            run_id="run-artemea-critical-handled-severity",
            dedupe_suffix="stockout_risk/product/sku-critical-handled-severity/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        handled.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        handled.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=3),
    )
    other = store.upsert_detection(
        _case_detection(
            business_id="other",
            severity="critical",
            run_id="run-other-critical-handled-severity",
            dedupe_suffix="stockout_risk/product/sku-other-critical-handled-severity/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        other.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/handling-latency/by-severity",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["handled_total"] == 1
    assert data["by_handling_bucket"] == {
        "under_1h": 0,
        "under_6h": 1,
        "under_24h": 0,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_handling_bucket_severity"]["under_6h"] == {"critical": 1}
    assert data["by_handling_bucket_severity"]["over_7d"] == {}
    assert data["fastest_handled"]["case_id"] == handled.case_id
    assert data["slowest_handled"]["case_id"] == handled.case_id


def test_internal_handling_latency_by_priority_bracket_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    high = store.upsert_detection(
        _case_detection(
            priority=95,
            run_id="run-artemea-high-handled",
            dedupe_suffix="stockout_risk/product/sku-high-handled/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        high.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        high.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=3),
    )
    medium = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-medium-handled",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        medium.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        medium.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=10),
    )
    low_other_tenant = store.upsert_detection(
        _case_detection(
            business_id="other",
            priority=20,
            run_id="run-other-low-handled",
            dedupe_suffix="stockout_risk/product/sku-low-handled/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        low_other_tenant.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        low_other_tenant.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/handling-latency/by-priority-bracket",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["handled_total"] == 2
    assert data["by_handling_bucket"] == {
        "under_1h": 0,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_handling_bucket_priority_bracket"]["under_6h"] == {"high": 1}
    assert data["by_handling_bucket_priority_bracket"]["under_24h"] == {"medium": 1}
    assert data["by_handling_bucket_priority_bracket"]["over_7d"] == {}
    assert data["fastest_handled"]["case_id"] == high.case_id
    assert data["slowest_handled"]["case_id"] == medium.case_id


def test_internal_handling_latency_by_case_type_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    stock = store.upsert_detection(
        _case_detection(
            case_type="stockout_risk",
            priority=95,
            run_id="run-artemea-stock-handled-case-type",
            dedupe_suffix="stockout_risk/product/sku-stock-handled-case-type/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        stock.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        stock.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=3),
    )
    sales = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-sales-handled-case-type",
            dedupe_suffix="sales_drop/channel/all/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        sales.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        sales.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=10),
    )
    other_tenant = store.upsert_detection(
        _case_detection(
            business_id="other",
            case_type="stockout_risk",
            run_id="run-other-handled-case-type",
            dedupe_suffix="stockout_risk/product/sku-other-handled-case-type/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other_tenant.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        other_tenant.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/handling-latency/by-case-type",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["handled_total"] == 2
    assert data["by_handling_bucket"] == {
        "under_1h": 0,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_handling_bucket_case_type"]["under_6h"] == {"stockout_risk": 1}
    assert data["by_handling_bucket_case_type"]["under_24h"] == {"sales_drop": 1}
    assert data["by_handling_bucket_case_type"]["over_7d"] == {}
    assert data["fastest_handled"]["case_id"] == stock.case_id
    assert data["slowest_handled"]["case_id"] == sales.case_id


def test_internal_handling_latency_by_entity_kind_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    product = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-product-handled-entity-kind",
            entity_scope={"kind": "product", "id": "sku-1", "label": "SKU 1"},
            dedupe_suffix="stockout_risk/product/sku-1/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        product.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        product.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=3),
    )
    channel = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-channel-handled-entity-kind",
            entity_scope={"kind": "channel", "id": "online", "label": "Online"},
            dedupe_suffix="sales_drop/channel/online/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        channel.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        channel.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=10),
    )
    other_tenant = store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-handled-entity-kind",
            entity_scope={"kind": "conversation", "id": "wa-1", "label": "Chat"},
            dedupe_suffix="stockout_risk/conversation/wa-1/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other_tenant.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        other_tenant.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/handling-latency/by-entity-kind",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["handled_total"] == 2
    assert data["by_handling_bucket"] == {
        "under_1h": 0,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_handling_bucket_entity_kind"] == {
        "under_1h": {},
        "under_6h": {"product": 1},
        "under_24h": {"channel": 1},
        "under_7d": {},
        "over_7d": {},
    }
    assert data["fastest_handled"]["case_id"] == product.case_id
    assert data["slowest_handled"]["case_id"] == channel.case_id
    assert "conversation" not in str(data)


def test_internal_handling_latency_by_source_connector_returns_scoped_envelope(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperationalCaseStore(conn)
    opened_at = datetime(2026, 5, 24, 8, tzinfo=timezone.utc)
    tiendanube = store.upsert_detection(
        _case_detection(
            run_id="run-artemea-tiendanube-handled-source",
            source="tiendanube",
            source_label="Tiendanube",
            dedupe_suffix="stockout_risk/product/sku-tiendanube-handled-source/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        tiendanube.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        tiendanube.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=3),
    )
    csv = store.upsert_detection(
        _case_detection(
            case_type="sales_drop",
            severity="warning",
            priority=70,
            run_id="run-artemea-csv-handled-source",
            source="csv",
            source_label="CSV import",
            dedupe_suffix="sales_drop/channel/csv/commerce.revenue/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        csv.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:juan",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        csv.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(hours=10),
    )
    other_tenant = store.upsert_detection(
        _case_detection(
            business_id="other",
            run_id="run-other-handled-source",
            source="meta_ads",
            source_label="Meta Ads",
            dedupe_suffix="stockout_risk/product/sku-other-handled-source/commerce.inventory/daily",
        ),
        detected_at=opened_at,
    )
    store.transition_case(
        other_tenant.case_id,
        status="acknowledged",
        actor_type="operator",
        actor_ref="operator:ana",
        transitioned_at=opened_at + timedelta(hours=1),
    )
    store.transition_case(
        other_tenant.case_id,
        status="resolved",
        actor_type="system",
        actor_ref="orvo_runtime",
        transitioned_at=opened_at + timedelta(days=8),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/cases/handling-latency/by-source-connector",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    assert body["redaction_applied"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["handled_total"] == 2
    assert data["by_handling_bucket"] == {
        "under_1h": 0,
        "under_6h": 1,
        "under_24h": 1,
        "under_7d": 0,
        "over_7d": 0,
    }
    assert data["by_handling_bucket_source_connector"] == {
        "under_1h": {},
        "under_6h": {"tiendanube": 1},
        "under_24h": {"csv": 1},
        "under_7d": {},
        "over_7d": {},
    }
    assert data["fastest_handled"]["case_id"] == tiendanube.case_id
    assert data["slowest_handled"]["case_id"] == csv.case_id
    assert "meta_ads" not in str(data)


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
        headers={
            "Authorization": "Bearer wrong access_token=raw_bad_bearer_secret",
            "X-Orvo-Operator": "operator:juan access_token=raw_bad_actor_secret",
            "X-Request-ID": "req-bad-token",
        },
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.get_json()["error"]["code"] == "unauthorized"
    assert wrong.get_json()["error"]["code"] == "unauthorized"
    assert "raw_bad_bearer_secret" not in wrong.get_data(as_text=True)
    assert "raw_bad_actor_secret" not in wrong.get_data(as_text=True)

    events = _audit_events(db_path)
    assert len(events) == 2
    missing_event = events[0]
    assert missing_event["business_id"] == "artemea"
    assert missing_event["actor_ref"] == "anonymous"
    assert missing_event["event_type"] == "operator.authentication.denied"
    assert missing_event["target_type"] == "internal_operator_api"
    assert missing_event["target_id"] == "artemea"
    assert missing_event["data"] == {
        "status": "denied",
        "reason": "missing_internal_token",
        "method": "GET",
        "header_present": False,
        "scheme": None,
    }
    event = events[1]
    assert event["business_id"] == "artemea"
    assert event["actor_ref"] == "[REDACTED]"
    assert event["event_type"] == "operator.authentication.denied"
    assert event["target_type"] == "internal_operator_api"
    assert event["target_id"] == "artemea"
    assert event["request_id"] == "req-bad-token"
    assert event["data"] == {
        "status": "denied",
        "reason": "invalid_internal_token",
        "method": "GET",
        "header_present": True,
        "scheme": "Bearer",
    }
    serialized = json.dumps(events, sort_keys=True)
    assert "raw_bad_bearer_secret" not in serialized
    assert "raw_bad_actor_secret" not in serialized


def test_internal_endpoints_audit_missing_bearer_token_attempt(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    _seed_case(db_path, _case_detection())

    response = client.get(
        "/internal/brain/businesses/artemea/cases",
        headers={"X-Orvo-Operator": "operator:missing-token", "X-Request-ID": "req-missing-token"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthorized"
    events = _audit_events(db_path)
    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "operator.authentication.denied"
    assert event["actor_ref"] == "operator:missing-token"
    assert event["request_id"] == "req-missing-token"
    assert event["data"] == {
        "status": "denied",
        "reason": "missing_internal_token",
        "method": "GET",
        "header_present": False,
        "scheme": None,
    }


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
        headers={
            **AUTH,
            "X-Orvo-Role": "operator",
            "X-Idempotency-Key": "case-action:artemea:audit-failed",
            "X-Request-ID": "req-failed",
        },
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
        headers={
            **AUTH,
            "X-Orvo-Role": "operator",
            "X-Idempotency-Key": "case-action:artemea:role-operator",
        },
        json={"action_key": "acknowledge_case"},
    )
    admin = client.post(
        f"/internal/brain/businesses/artemea/cases/{admin_case.case_id}/actions",
        headers={
            **AUTH,
            "X-Orvo-Role": "admin",
            "X-Orvo-Operator": "admin:sol",
            "X-Idempotency-Key": "case-action:artemea:admin",
        },
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


def test_internal_operator_audit_export_denial_writes_redacted_audit_event(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/operator-audit-events?limit=10",
        headers={
            **AUTH,
            "X-Orvo-Role": "operator",
            "X-Orvo-Operator": "operator:juan access_token=raw_denial_actor_secret",
            "X-Orvo-Businesses": "artemea, demo-secret access_token=raw_denial_grant_secret",
            "X-Request-ID": "req-audit-export-denied",
        },
    )

    assert response.status_code == 403
    raw_body = response.get_data(as_text=True)
    assert "raw_denial_actor_secret" not in raw_body
    assert "raw_denial_grant_secret" not in raw_body
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "forbidden"
    assert body["redaction_applied"] is True
    events = _audit_events(db_path)
    assert len(events) == 1
    event = events[0]
    assert event["business_id"] == "artemea"
    assert event["actor_ref"] == "[REDACTED]"
    assert event["event_type"] == "operator.authorization.denied"
    assert event["target_type"] == "internal_operator_api"
    assert event["target_id"] == "artemea"
    assert event["request_id"] == "req-audit-export-denied"
    assert event["data"]["reason"] == "missing_permission"
    assert event["data"]["permission"] == "operator_audit:read"
    assert event["data"]["role"] == "operator"
    serialized = json.dumps(event, sort_keys=True)
    assert "raw_denial_actor_secret" not in serialized
    assert "raw_denial_grant_secret" not in serialized


def test_internal_operator_audit_export_is_admin_only_and_redacted(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    case = _seed_case(db_path, _case_detection())
    failure = client.post(
        f"/internal/brain/businesses/artemea/cases/{case.case_id}/actions",
        headers={
            **AUTH,
            "X-Orvo-Role": "operator",
            "X-Idempotency-Key": "case-action:artemea:audit-export-source",
            "X-Request-ID": "req-audit-source",
        },
        json={
            "action_key": "unknown_action",
            "comment": "Authorization: Basic " + "cmF3X2F1ZGl0X3NlY3JldA==",
            "metadata": {"access_token": "raw_audit_secret"},
        },
    )
    assert failure.status_code == 400

    operator = client.get(
        "/internal/brain/businesses/artemea/operator-audit-events?limit=10",
        headers={**AUTH, "X-Orvo-Role": "operator", "X-Request-ID": "req-audit-export-denied"},
    )
    admin = client.get(
        "/internal/brain/businesses/artemea/operator-audit-events?limit=10",
        headers={**AUTH, "X-Orvo-Role": "admin", "X-Orvo-Operator": "admin:sol"},
    )

    assert operator.status_code == 403
    assert operator.get_json()["error"]["code"] == "forbidden"
    assert admin.status_code == 200
    raw_body = admin.get_data(as_text=True)
    assert "raw_audit_secret" not in raw_body
    assert "cmF3X2F1ZGl0X3NlY3JldA==" not in raw_body
    body = admin.get_json()
    assert body["ok"] is True
    assert body["redaction_applied"] is True
    assert body["data"]["limit"] == 10
    assert body["data"]["count"] == 2
    events_by_request = {event["request_id"]: event for event in body["data"]["events"]}
    event = events_by_request["req-audit-source"]
    assert event["business_id"] == "artemea"
    assert event["actor_ref"] == "operator:juan"
    assert event["event_type"] == "operator.case_action.failed"
    assert event["target_type"] == "operational_case"
    assert event["target_id"] == case.case_id
    assert event["data"]["error_code"] == "unknown_action_key"
    assert event["data"]["payload"]["metadata"]["access_token"] == "[REDACTED]"
    denial = events_by_request["req-audit-export-denied"]
    assert denial["event_type"] == "operator.authorization.denied"
    assert denial["data"]["permission"] == "operator_audit:read"


def test_internal_operator_audit_export_orders_by_occurred_at_not_insert_order(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperatorAuditStore(conn)
    newer_id = store.append_event(
        business_id="artemea",
        actor_ref="operator:newer",
        event_type="operator.case_action.failed",
        target_type="operational_case",
        data={},
        created_at=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )
    older_id = store.append_event(
        business_id="artemea",
        actor_ref="operator:older",
        event_type="operator.case_action.failed",
        target_type="operational_case",
        data={},
        created_at=datetime(2026, 5, 24, 9, tzinfo=timezone.utc),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/operator-audit-events?limit=10",
        headers={**AUTH, "X-Orvo-Role": "admin", "X-Orvo-Operator": "admin:sol"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert [event["event_id"] for event in body["data"]["events"]] == [newer_id, older_id]


def test_internal_operator_audit_export_rejects_invalid_and_non_positive_limits(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    invalid = client.get(
        "/internal/brain/businesses/artemea/operator-audit-events?limit=not-an-int",
        headers={**AUTH, "X-Orvo-Role": "admin", "X-Orvo-Operator": "admin:sol"},
    )
    zero = client.get(
        "/internal/brain/businesses/artemea/operator-audit-events?limit=0",
        headers={**AUTH, "X-Orvo-Role": "admin", "X-Orvo-Operator": "admin:sol"},
    )

    assert invalid.status_code == 400
    assert invalid.get_json()["error"]["code"] == "invalid_limit"
    assert zero.status_code == 400
    assert zero.get_json()["error"]["code"] == "invalid_limit"


def test_internal_operator_audit_export_caps_limit_at_200(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperatorAuditStore(conn)
    now = datetime.now(timezone.utc)
    for index in range(205):
        store.append_event(
            business_id="artemea",
            actor_ref=f"operator:{index}",
            event_type="operator.case_action.failed",
            target_type="operational_case",
            data={},
            created_at=now - timedelta(seconds=index),
        )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/operator-audit-events?limit=500",
        headers={**AUTH, "X-Orvo-Role": "admin", "X-Orvo-Operator": "admin:sol"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["data"]["limit"] == 200
    assert body["data"]["count"] == 200
    assert len(body["data"]["events"]) == 200


def test_internal_operator_audit_export_enforces_retention_window(monkeypatch, tmp_path):
    client, db_path = _client(monkeypatch, tmp_path)
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    store = SQLiteOperatorAuditStore(conn)
    old_id = store.append_event(
        business_id="artemea",
        actor_ref="operator:old",
        event_type="operator.case_action.failed",
        target_type="operational_case",
        data={"access_token": "old_raw_audit_secret"},
        created_at=now - timedelta(days=91),
    )
    recent_id = store.append_event(
        business_id="artemea",
        actor_ref="operator:recent",
        event_type="operator.case_action.failed",
        target_type="operational_case",
        data={"access_token": "recent_raw_audit_secret"},
        created_at=now - timedelta(days=3),
    )
    conn.close()

    response = client.get(
        "/internal/brain/businesses/artemea/operator-audit-events?limit=10",
        headers={**AUTH, "X-Orvo-Role": "admin", "X-Orvo-Operator": "admin:sol"},
    )

    assert response.status_code == 200
    raw_body = response.get_data(as_text=True)
    assert "old_raw_audit_secret" not in raw_body
    assert "recent_raw_audit_secret" not in raw_body
    body = response.get_json()
    assert body["data"]["retention_days"] == 90
    assert [event["event_id"] for event in body["data"]["events"]] == [recent_id]
    assert old_id not in raw_body


def test_internal_operator_audit_export_rejects_retention_abuse(monkeypatch, tmp_path):
    client, _db_path = _client(monkeypatch, tmp_path)

    response = client.get(
        "/internal/brain/businesses/artemea/operator-audit-events?retention_days=3650",
        headers={**AUTH, "X-Orvo-Role": "admin", "X-Orvo-Operator": "admin:sol"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_retention_days"
    assert body["redaction_applied"] is True

"""HTTP endpoint tests for internal workflow approval/execution/audit projections."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import pytest

from app.brain.storage import init_schema
from app.brain.workflow_action_ledger import SQLiteWorkflowActionLedgerStore


AUTH = {"Authorization": "Bearer test-internal-token"}


def utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 13, hour, minute, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test_brain.sqlite3"
    monkeypatch.setenv("ORVO_BRAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ORVO_INTERNAL_OPERATOR_TOKEN", "test-internal-token")
    with closing(sqlite3.connect(str(db_path))) as conn:
        init_schema(conn)
    yield db_path


def _seed_workflow_actions(db_path):
    ledger = SQLiteWorkflowActionLedgerStore(str(db_path))
    pending = ledger.record_planned_action(
        business_id="artemea",
        case_id="case-pending",
        action_key="request_external_action",
        idempotency_key="workflow/artemea/http/pending",
        execution_state="blocked_approval_required",
        approval_required=True,
        source="workflow",
        actor_ref="operator",
        params={
            "target": "supplier-a",
            "reason": "Pending Authorization: Basic raw_pending_secret",
        },
        rule_id="http-workflow-pending",
        now=utc(9, 0),
    )
    approved = ledger.record_planned_action(
        business_id="artemea",
        case_id="case-approved",
        action_key="request_external_action",
        idempotency_key="workflow/artemea/http/approved",
        execution_state="blocked_approval_required",
        approval_required=True,
        source="workflow",
        actor_ref="operator",
        params={
            "target": "supplier-b",
            "reason": "Approved Authorization: Basic raw_approved_secret",
        },
        rule_id="http-workflow-approved",
        now=utc(8, 30),
    )
    ledger.record_planned_action(
        business_id="other-business",
        case_id="case-other",
        action_key="request_external_action",
        idempotency_key="workflow/other/http/approved",
        execution_state="blocked_approval_required",
        approval_required=True,
        params={"target": "supplier-z", "reason": "Other business"},
        rule_id="http-workflow-other",
        now=utc(8, 0),
    )

    assert pending.approval_request is not None
    assert approved.approval_request is not None
    ledger.decide_approval_request(
        business_id="artemea",
        approval_request_id=approved.approval_request.approval_request_id,
        decision="approved",
        actor_ref="manager",
        reason="Approved Authorization: Basic raw_decision_secret",
        now=utc(8, 45),
    )
    return pending, approved


def test_internal_workflow_approval_queue_returns_redacted_pending_requests(_isolate_db):
    from server import app

    pending, approved = _seed_workflow_actions(_isolate_db)

    response = app.test_client().get(
        "/internal/brain/businesses/artemea/workflow/approval-queue?limit=1",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["business_id"] == "artemea"
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["approval_execution_enabled"] is False
    assert data["side_effects_executed"] == 0
    assert data["total"] == 1
    assert data["returned"] == 1
    assert [item["approval_request_id"] for item in data["approval_requests"]] == [
        pending.approval_request.approval_request_id
    ]
    assert data["approval_requests"][0]["case_id"] == "case-pending"
    assert data["approval_requests"][0]["params"]["reason"] == "Pending Authorization: [REDACTED]"
    assert approved.approval_request.approval_request_id not in str(data)
    assert "raw_pending_secret" not in str(data)


def test_internal_workflow_execution_queue_can_scope_to_case_and_redacts_params(_isolate_db):
    from server import app

    pending, approved = _seed_workflow_actions(_isolate_db)
    client = app.test_client()

    invalid = client.get(
        "/internal/brain/businesses/artemea/workflow/execution-queue?case_id=+++",
        headers=AUTH,
    )
    assert invalid.status_code == 400
    invalid_body = invalid.get_json()
    assert invalid_body["ok"] is False
    assert invalid_body["error"]["code"] == "invalid_workflow_execution_queue_scope"

    response = client.get(
        "/internal/brain/businesses/artemea/workflow/execution-queue?case_id=case-approved",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["case_id"] == "case-approved"
    assert data["execution_enabled"] is False
    assert data["side_effects_executed"] == 0
    assert data["total"] == 1
    assert data["returned"] == 1
    assert [action["ledger_id"] for action in data["actions"]] == [approved.record.ledger_id]
    assert data["actions"][0]["params"]["reason"] == "Approved Authorization: [REDACTED]"
    assert pending.record.ledger_id not in str(data)
    assert "raw_approved_secret" not in str(data)


def test_internal_workflow_action_audit_events_validate_scope_and_return_redacted_history(_isolate_db):
    from server import app

    pending, approved = _seed_workflow_actions(_isolate_db)
    client = app.test_client()

    invalid = client.get(
        "/internal/brain/businesses/artemea/workflow/action-audit-events?case_id=+++",
        headers=AUTH,
    )
    assert invalid.status_code == 400
    invalid_body = invalid.get_json()
    assert invalid_body["ok"] is False
    assert invalid_body["error"]["code"] == "invalid_workflow_audit_scope"

    response = client.get(
        "/internal/brain/businesses/artemea/workflow/action-audit-events?case_id=case-approved",
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    data = body["data"]
    assert data["business_id"] == "artemea"
    assert data["case_id"] == "case-approved"
    assert data["audit_projection_enabled"] is True
    assert data["side_effects_executed"] == 0
    assert data["total"] == 3
    assert data["returned"] == 3
    assert [event["event_type"] for event in data["events"]] == [
        "workflow_action_planned",
        "workflow_approval_requested",
        "workflow_approval_decided",
    ]
    assert {event["ledger_id"] for event in data["events"]} == {approved.record.ledger_id}
    assert pending.record.ledger_id not in str(data)
    assert data["events"][-1]["decision_reason"] == "Approved Authorization: [REDACTED]"
    assert "raw_decision_secret" not in str(data)

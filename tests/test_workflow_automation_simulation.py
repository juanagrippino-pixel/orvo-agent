from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.brain.operational_cases import (
    InMemoryOperationalCaseStore,
    OperationalCaseDetection,
    OperationalCaseEvidenceSnapshot,
)
from app.brain.action_catalog import (
    API_ENABLED_CASE_ACTION_KEYS,
    ACTION_CATALOG,
    list_case_action_catalog,
)
from app.brain.workflow_automation import (
    CaseWorkflowCondition,
    WORKFLOW_ACTION_REGISTRY,
    WorkflowAction,
    WorkflowAutomationError,
    WorkflowRule,
    make_workflow_idempotency_key,
    simulate_case_workflow,
)
from app.brain.workflow_action_ledger import (
    InMemoryWorkflowActionLedgerStore,
    SQLiteWorkflowActionLedgerStore,
    WorkflowActionLedgerRecord,
    WorkflowActionLedgerError,
    WorkflowApprovalRequest,
)
from app.brain.workflow_action_audit import list_workflow_action_audit_events
from app.brain.workflow_approval_queue import list_workflow_approval_queue
from app.brain.workflow_execution_queue import list_workflow_execution_queue


def utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 31, hour, minute, tzinfo=timezone.utc)


def case_detection(
    *,
    business_id: str = "artemea",
    priority_score: int = 95,
    degraded: bool = False,
) -> OperationalCaseDetection:
    snapshots = []
    if degraded:
        snapshots.append(
            OperationalCaseEvidenceSnapshot(
                snapshot_key=f"{business_id}/stockout/stale-source",
                evidence_ref=f"evidence://{business_id}/run-1/stockout_risk",
                source="commerce.inventory",
                case_type="stockout_risk",
                summary="Inventory connector stale",
                freshness_state="stale",
            )
        )
    return OperationalCaseDetection(
        business_id=business_id,
        case_type="stockout_risk",
        dedupe_key=f"{business_id}/stockout_risk/product/sku-1/commerce.inventory/daily",
        title="Stock crítico token=raw_case_title_secret",
        severity="critical",
        priority_score=priority_score,
        entity_scope={"kind": "product", "id": "sku-1", "label": "SKU 1"},
        evidence_refs=[f"evidence://{business_id}/run-1/stockout_risk"],
        run_id="run-1",
        artifact_refs=["ledger://runs/run-1/daily-report"],
        evidence_snapshots=snapshots,
        metadata={"source": "test"},
    )


def seed_case(priority_score: int = 95, degraded: bool = False):
    store = InMemoryOperationalCaseStore()
    case = store.upsert_detection(case_detection(priority_score=priority_score, degraded=degraded), detected_at=utc(8))
    return store, case


def test_action_catalog_is_canonical_for_workflow_and_operator_projections():
    projection = list_case_action_catalog(business_id="artemea")
    actions = {action["action_key"]: action for action in projection["actions"]}

    assert set(WORKFLOW_ACTION_REGISTRY) == set(ACTION_CATALOG)
    assert projection["business_id"] == "artemea"
    assert projection["api_enabled_action_keys"] == list(API_ENABLED_CASE_ACTION_KEYS)
    assert set(projection["api_enabled_action_keys"]) == {
        "acknowledge_case",
        "add_comment",
        "assign_owner",
        "dismiss_case",
        "mark_in_progress",
        "resolve_case",
    }
    assert actions["resolve_case"]["requires_reason"] is True
    assert actions["dismiss_case"]["requires_reason"] is True
    assert actions["request_external_action"]["api_enabled"] is False
    assert actions["request_external_action"]["approval_required"] is True


def test_simulate_case_workflow_dry_run_plans_whitelisted_action_without_mutating_case():
    store, case = seed_case()
    original_status = case.status
    original_timeline_count = len(case.timeline)
    rule = WorkflowRule(
        rule_id="critical-stock-ack",
        business_id="artemea",
        trigger="case_updated",
        conditions=[
            CaseWorkflowCondition(field="status", value="open"),
            CaseWorkflowCondition(field="case_type", value="stockout_risk"),
            CaseWorkflowCondition(field="min_priority_score", value=90),
        ],
        actions=[
            WorkflowAction(
                action_key="acknowledge_case",
                params={"reason": "Auto-triage candidate token=raw_action_secret"},
            )
        ],
    )

    result = simulate_case_workflow(rule, case, now=utc(9))

    assert result["matched"] is True
    assert result["side_effects_executed"] == 0
    assert result["conditions"] == [
        {"field": "status", "expected": "open", "actual": "open", "matched": True},
        {"field": "case_type", "expected": "stockout_risk", "actual": "stockout_risk", "matched": True},
        {"field": "min_priority_score", "expected": 90, "actual": 95, "matched": True},
    ]
    planned_action = result["actions"][0]
    assert planned_action["action_key"] == "acknowledge_case"
    assert planned_action["execution_status"] == "dry_run"
    assert planned_action["requires_approval"] is False
    assert planned_action["idempotency_key"] == make_workflow_idempotency_key(
        business_id="artemea",
        rule_id="critical-stock-ack",
        case_id=case.case_id,
        action_key="acknowledge_case",
        params={"reason": "Auto-triage candidate token=raw_action_secret"},
    )
    assert planned_action["audit_event"] == {
        "event_type": "workflow_action_planned",
        "rule_id": "critical-stock-ack",
        "case_id": case.case_id,
        "action_key": "acknowledge_case",
        "idempotency_key": planned_action["idempotency_key"],
        "execution_status": "dry_run",
        "created_at": "2026-05-31T09:00:00Z",
    }
    assert "raw_action_secret" not in str(result)
    assert "raw_case_title_secret" not in str(result)

    reloaded = store.get_case(case.case_id)
    assert reloaded is not None
    assert reloaded.status == original_status
    assert len(reloaded.timeline) == original_timeline_count


def test_simulate_case_workflow_blocks_external_action_behind_approval_gate_and_redacts_params():
    _, case = seed_case()
    rule = WorkflowRule(
        rule_id="external-restock-request",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="status", value="open")],
        actions=[
            WorkflowAction(
                action_key="request_external_action",
                params={
                    "target": "supplier",
                    "reason": "Ask supplier for emergency restock",
                    "Authorization": "Basic raw_external_secret",
                },
            )
        ],
    )

    result = simulate_case_workflow(rule, case, now=utc(10))

    planned_action = result["actions"][0]
    assert planned_action["action_key"] == "request_external_action"
    assert planned_action["mode"] == "approval_required"
    assert planned_action["requires_approval"] is True
    assert planned_action["approval_gate"] == {
        "required": True,
        "state": "pending_approval",
        "reason": "approval_required_before_execution",
    }
    assert planned_action["execution_status"] == "blocked_approval_required"
    assert planned_action["side_effect"] == "external"
    assert "raw_external_secret" not in str(result)
    assert planned_action["params"]["Authorization"] == "[REDACTED]"


@pytest.mark.parametrize(
    ("action", "expected_missing"),
    [
        (WorkflowAction(action_key="resolve_case", params={}), "reason"),
        (WorkflowAction(action_key="dismiss_case", params={"reason": "   "}), "reason"),
        (WorkflowAction(action_key="request_external_action", params={"Authorization": "Basic raw_missing_reason_secret"}), "reason"),
        (WorkflowAction(action_key="add_comment", params={}), "comment"),
        (WorkflowAction(action_key="assign_owner", params={"assignee_ref": ""}), "assignee_ref"),
    ],
)
def test_simulate_case_workflow_rejects_actions_missing_catalog_required_params(action, expected_missing):
    _, case = seed_case()
    rule = WorkflowRule(
        rule_id=f"missing-{action.action_key}-param",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="status", value="open")],
        actions=[action],
    )

    with pytest.raises(WorkflowAutomationError) as exc:
        simulate_case_workflow(rule, case, now=utc(10, 30))

    assert exc.value.code == "missing_workflow_action_params"
    assert action.action_key in exc.value.message
    assert expected_missing in exc.value.message
    assert "raw_missing_reason_secret" not in exc.value.message


def test_workflow_idempotency_keys_are_stable_across_secret_rotation_but_sensitive_to_action_intent():
    _, case = seed_case()
    base_params = {"target": "supplier-a", "Authorization": "Basic " + "rotated_external_secret_a"}
    rotated_secret_params = {"target": "supplier-a", "Authorization": "Basic " + "rotated_external_secret_b"}
    changed_intent_params = {"target": "supplier-b", "Authorization": "Basic " + "rotated_external_secret_a"}

    base_key = make_workflow_idempotency_key(
        business_id="artemea",
        rule_id="external-restock-request",
        case_id=case.case_id,
        action_key="request_external_action",
        params=base_params,
    )
    rotated_secret_key = make_workflow_idempotency_key(
        business_id="artemea",
        rule_id="external-restock-request",
        case_id=case.case_id,
        action_key="request_external_action",
        params=rotated_secret_params,
    )
    changed_intent_key = make_workflow_idempotency_key(
        business_id="artemea",
        rule_id="external-restock-request",
        case_id=case.case_id,
        action_key="request_external_action",
        params=changed_intent_params,
    )

    assert rotated_secret_key == base_key
    assert changed_intent_key != base_key
    assert "rotated_external_secret" not in base_key
    assert base_key.startswith(f"workflow/artemea/external-restock-request/{case.case_id}/request_external_action/")


def test_simulate_case_workflow_rejects_unknown_action_key_before_projecting_actions():
    _, case = seed_case(priority_score=10)
    rule = WorkflowRule(
        rule_id="unknown-action",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="min_priority_score", value=90)],
        actions=[WorkflowAction(action_key="invented_llm_action", params={})],
    )

    with pytest.raises(WorkflowAutomationError) as exc:
        simulate_case_workflow(rule, case, now=utc(11))

    assert exc.value.code == "unknown_workflow_action_key"


def test_simulate_case_workflow_rejects_action_key_for_unregistered_case_family():
    _, case = seed_case()
    rule = WorkflowRule(
        rule_id="wrong-family-suggestion",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="status", value="open")],
        actions=[WorkflowAction(action_key="check_storefront", params={})],
    )

    with pytest.raises(WorkflowAutomationError) as exc:
        simulate_case_workflow(rule, case, now=utc(11))

    assert exc.value.code == "action_not_allowed_for_case_type"


def test_simulate_case_workflow_rejects_unknown_trigger_before_projecting_actions():
    _, case = seed_case()
    rule = WorkflowRule(
        rule_id="unknown-trigger",
        business_id="artemea",
        trigger="case_deleted",  # type: ignore[arg-type]
        conditions=[CaseWorkflowCondition(field="status", value="open")],
        actions=[WorkflowAction(action_key="acknowledge_case", params={})],
    )

    with pytest.raises(WorkflowAutomationError) as exc:
        simulate_case_workflow(rule, case, now=utc(11))

    assert exc.value.code == "unsupported_workflow_trigger"


def test_simulate_case_workflow_rejects_cross_business_rule_before_projecting_actions():
    _, case = seed_case()
    rule = WorkflowRule(
        rule_id="cross-tenant-ack",
        business_id="other-business",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="status", value="open")],
        actions=[
            WorkflowAction(
                action_key="acknowledge_case",
                params={"Authorization": "Basic " + "cross_tenant_secret"},
            )
        ],
    )

    with pytest.raises(WorkflowAutomationError) as exc:
        simulate_case_workflow(rule, case, now=utc(11))

    assert exc.value.code == "business_scope_mismatch"
    assert "cross_tenant_secret" not in str(exc.value)


def test_simulate_case_workflow_returns_no_actions_when_conditions_do_not_match():
    _, case = seed_case(priority_score=40)
    rule = WorkflowRule(
        rule_id="critical-only",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="min_priority_score", value=90)],
        actions=[WorkflowAction(action_key="acknowledge_case", params={})],
    )

    result = simulate_case_workflow(rule, case, now=utc(12))

    assert result["matched"] is False
    assert result["actions"] == []
    assert result["conditions"] == [
        {"field": "min_priority_score", "expected": 90, "actual": 40, "matched": False}
    ]
    assert result["non_match_reasons"] == [
        {"type": "condition_mismatch", "field": "min_priority_score", "expected": 90, "actual": 40}
    ]
    assert result["side_effects_executed"] == 0


def test_simulate_case_workflow_projects_trigger_and_condition_non_match_reasons_without_ledger_writes():
    _, case = seed_case(priority_score=40)
    ledger = InMemoryWorkflowActionLedgerStore()
    rule = WorkflowRule(
        rule_id="manual-critical-only",
        business_id="artemea",
        trigger="manual",
        conditions=[
            CaseWorkflowCondition(field="status", value="open"),
            CaseWorkflowCondition(field="min_priority_score", value=90),
            CaseWorkflowCondition(field="severity", value="critical token=raw_non_match_condition_secret"),
        ],
        actions=[
            WorkflowAction(
                action_key="acknowledge_case",
                params={"reason": "Do not leak token=raw_non_match_reason_secret"},
            )
        ],
    )

    result = simulate_case_workflow(
        rule,
        case,
        now=utc(12, 10),
        action_ledger=ledger,
        event_trigger="case_updated",
    )

    assert result["matched"] is False
    assert result["actions"] == []
    assert result["skipped_actions"] == []
    assert result["non_match_reasons"] == [
        {"type": "trigger_mismatch", "expected": "manual", "actual": "case_updated"},
        {"type": "condition_mismatch", "field": "min_priority_score", "expected": 90, "actual": 40},
        {
            "type": "condition_mismatch",
            "field": "severity",
            "expected": "critical token=[REDACTED]",
            "actual": "critical",
        },
    ]
    assert result["side_effects_executed"] == 0
    assert ledger.list_actions(business_id="artemea") == []
    assert "raw_non_match" not in str(result)


def test_simulate_case_workflow_returns_no_actions_when_event_trigger_does_not_match_rule_trigger():
    _, case = seed_case()
    ledger = InMemoryWorkflowActionLedgerStore()
    rule = WorkflowRule(
        rule_id="opened-only-ack",
        business_id="artemea",
        trigger="case_opened",
        conditions=[CaseWorkflowCondition(field="status", value="open")],
        actions=[WorkflowAction(action_key="acknowledge_case", params={})],
    )

    result = simulate_case_workflow(
        rule,
        case,
        now=utc(12, 30),
        action_ledger=ledger,
        actor_ref="operator:ana",
        event_trigger="case_updated",
    )

    assert result["matched"] is False
    assert result["trigger_match"] == {"expected": "case_opened", "actual": "case_updated", "matched": False}
    assert result["conditions"] == [{"field": "status", "expected": "open", "actual": "open", "matched": True}]
    assert result["actions"] == []
    assert result["skipped_actions"] == []
    assert result["side_effects_executed"] == 0
    assert ledger.list_actions(business_id="artemea") == []
    assert ledger.list_approval_requests(business_id="artemea") == []


def test_simulate_case_workflow_matches_degraded_condition_from_evidence_snapshots():
    _, case = seed_case(degraded=True)
    rule = WorkflowRule(
        rule_id="degraded-stock-follow-up",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="degraded", value=True)],
        actions=[WorkflowAction(action_key="request_follow_up", params={"note": "Check stale connector"})],
    )

    result = simulate_case_workflow(rule, case, now=utc(13))

    assert result["matched"] is True
    assert result["conditions"] == [
        {"field": "degraded", "expected": True, "actual": True, "matched": True}
    ]
    assert result["actions"][0]["action_key"] == "request_follow_up"
    assert result["actions"][0]["execution_status"] == "dry_run"


def test_simulate_case_workflow_matches_source_connector_condition_from_evidence_snapshots():
    _, case = seed_case(degraded=True)
    ledger = InMemoryWorkflowActionLedgerStore()
    rule = WorkflowRule(
        rule_id="inventory-connector-follow-up",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="source_connector", value="commerce.inventory")],
        actions=[WorkflowAction(action_key="request_follow_up", params={"note": "Check inventory connector"})],
    )

    result = simulate_case_workflow(rule, case, now=utc(13, 15), action_ledger=ledger)

    assert result["matched"] is True
    assert result["conditions"] == [
        {
            "field": "source_connector",
            "expected": "commerce.inventory",
            "actual": ["commerce.inventory"],
            "matched": True,
        }
    ]
    assert result["actions"][0]["action_key"] == "request_follow_up"
    assert result["actions"][0]["execution_status"] == "dry_run"
    assert len(ledger.list_actions(business_id="artemea")) == 1


def test_simulate_case_workflow_suppresses_actions_when_source_connector_does_not_match():
    _, case = seed_case(degraded=True)
    ledger = InMemoryWorkflowActionLedgerStore()
    rule = WorkflowRule(
        rule_id="sheets-only-follow-up",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="source_connector", value="google_sheets")],
        actions=[WorkflowAction(action_key="request_follow_up", params={"note": "Check sheets connector"})],
    )

    result = simulate_case_workflow(rule, case, now=utc(13, 30), action_ledger=ledger)

    assert result["matched"] is False
    assert result["conditions"] == [
        {
            "field": "source_connector",
            "expected": "google_sheets",
            "actual": ["commerce.inventory"],
            "matched": False,
        }
    ]
    assert result["actions"] == []
    assert result["skipped_actions"] == []
    assert ledger.list_actions(business_id="artemea") == []


def test_simulate_case_workflow_suppresses_duplicate_idempotency_key_plans_with_audit():
    _, case = seed_case()
    duplicate_params = {"reason": "token=raw_duplicate_secret"}
    expected_key = make_workflow_idempotency_key(
        business_id="artemea",
        rule_id="duplicate-ack-plan",
        case_id=case.case_id,
        action_key="acknowledge_case",
        params=duplicate_params,
    )
    rule = WorkflowRule(
        rule_id="duplicate-ack-plan",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="status", value="open")],
        actions=[
            WorkflowAction(action_key="acknowledge_case", params=duplicate_params),
            WorkflowAction(action_key="acknowledge_case", params=duplicate_params),
        ],
    )

    result = simulate_case_workflow(rule, case, now=utc(14))

    assert result["side_effects_executed"] == 0
    assert [action["idempotency_key"] for action in result["actions"]] == [expected_key]
    assert result["skipped_actions"] == [
        {
            "action_key": "acknowledge_case",
            "idempotency_key": expected_key,
            "execution_status": "skipped_duplicate",
            "reason": "duplicate_idempotency_key",
            "audit_event": {
                "event_type": "workflow_action_skipped_duplicate",
                "rule_id": "duplicate-ack-plan",
                "case_id": case.case_id,
                "action_key": "acknowledge_case",
                "idempotency_key": expected_key,
                "execution_status": "skipped_duplicate",
                "reason": "duplicate_idempotency_key",
                "created_at": "2026-05-31T14:00:00Z",
            },
        }
    ]
    assert "raw_duplicate_secret" not in str(result)


def test_workflow_action_ledger_records_approval_request_without_external_side_effects(tmp_path):
    _, case = seed_case()
    ledger = SQLiteWorkflowActionLedgerStore(str(tmp_path / "workflow-actions.sqlite3"))
    rule = WorkflowRule(
        rule_id="durable-external-restock",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="status", value="open")],
        actions=[
            WorkflowAction(
                action_key="request_external_action",
                params={
                    "target": "supplier",
                    "reason": "Request emergency supplier restock",
                    "Authorization": "Basic raw_approval_secret",
                },
            )
        ],
    )

    result = simulate_case_workflow(rule, case, now=utc(15), action_ledger=ledger, actor_ref="operator:ana")

    assert result["side_effects_executed"] == 0
    planned_action = result["actions"][0]
    assert planned_action["execution_status"] == "blocked_approval_required"
    assert planned_action["approval_state"] == "pending"
    assert planned_action["ledger_id"].startswith("workflow-action/")
    assert planned_action["approval_request_id"].startswith("workflow-approval/")
    assert "raw_approval_secret" not in str(result)

    [record] = ledger.list_actions(business_id="artemea")
    assert record.action_key == "request_external_action"
    assert record.actor_ref == "operator:ana"
    assert record.source == "workflow"
    assert record.execution_state == "blocked_approval_required"
    assert record.approval_state == "pending"
    assert record.params["Authorization"] == "[REDACTED]"
    assert "raw_approval_secret" not in str(record)

    [approval] = ledger.list_approval_requests(business_id="artemea")
    assert approval.ledger_id == record.ledger_id
    assert approval.status == "pending"
    assert approval.requester_ref == "operator:ana"
    assert approval.action_key == "request_external_action"


def test_workflow_action_ledger_enforces_duplicate_idempotency_keys_across_store_instances(tmp_path):
    _, case = seed_case()
    db_path = tmp_path / "workflow-actions.sqlite3"
    first_ledger = SQLiteWorkflowActionLedgerStore(str(db_path))
    rule = WorkflowRule(
        rule_id="durable-duplicate-ack",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="status", value="open")],
        actions=[WorkflowAction(action_key="acknowledge_case", params={"reason": "token=raw_durable_duplicate"})],
    )

    first = simulate_case_workflow(rule, case, now=utc(16), action_ledger=first_ledger, actor_ref="operator:ana")
    second_ledger = SQLiteWorkflowActionLedgerStore(str(db_path))
    second = simulate_case_workflow(rule, case, now=utc(16, 5), action_ledger=second_ledger, actor_ref="operator:ana")

    assert len(first["actions"]) == 1
    assert first["actions"][0]["execution_status"] == "dry_run"
    assert first["actions"][0]["approval_state"] == "not_required"
    assert second["actions"] == []
    assert second["skipped_actions"] == [
        {
            "action_key": "acknowledge_case",
            "idempotency_key": first["actions"][0]["idempotency_key"],
            "execution_status": "skipped_duplicate",
            "reason": "duplicate_idempotency_key",
            "ledger_id": first["actions"][0]["ledger_id"],
            "audit_event": {
                "event_type": "workflow_action_skipped_duplicate",
                "rule_id": "durable-duplicate-ack",
                "case_id": case.case_id,
                "action_key": "acknowledge_case",
                "idempotency_key": first["actions"][0]["idempotency_key"],
                "execution_status": "skipped_duplicate",
                "reason": "duplicate_idempotency_key",
                "created_at": "2026-05-31T16:05:00Z",
            },
        }
    ]
    assert len(second_ledger.list_actions(business_id="artemea")) == 1
    assert second_ledger.list_approval_requests(business_id="artemea") == []
    assert "raw_durable_duplicate" not in str(first)
    assert "raw_durable_duplicate" not in str(second)


@pytest.mark.parametrize(
    "store_factory",
    [
        lambda tmp_path: InMemoryWorkflowActionLedgerStore(),
        lambda tmp_path: SQLiteWorkflowActionLedgerStore(str(tmp_path / "workflow-actions.sqlite3")),
    ],
)
def test_workflow_approval_decision_approves_pending_gate_without_executing_side_effects(tmp_path, store_factory):
    _, case = seed_case()
    ledger = store_factory(tmp_path)
    rule = WorkflowRule(
        rule_id="approve-external-restock",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="status", value="open")],
        actions=[
            WorkflowAction(
                action_key="request_external_action",
                params={
                    "target": "supplier",
                    "reason": "Request supplier restock",
                    "Authorization": "Basic raw_decision_planning_secret",
                },
            )
        ],
    )
    planned = simulate_case_workflow(rule, case, now=utc(17), action_ledger=ledger, actor_ref="operator:ana")
    approval_request_id = planned["actions"][0]["approval_request_id"]

    decision = ledger.decide_approval_request(
        business_id="artemea",
        approval_request_id=approval_request_id,
        decision="approved",
        actor_ref="manager token=raw_decision_actor_secret",
        reason="Approved after call Authorization: Basic raw_decision_reason_secret",
        now=utc(17, 30),
    )

    assert decision.record.approval_state == "approved"
    assert decision.record.execution_state == "pending_execution"
    assert decision.approval_request.status == "approved"
    assert decision.approval_request.decided_at == utc(17, 30)
    assert decision.approval_request.decision_actor_ref == "manager token=[REDACTED]"
    assert decision.approval_request.decision_reason == "Approved after call Authorization: [REDACTED]"
    assert decision.side_effects_executed == 0
    assert decision.audit_event == {
        "event_type": "workflow_approval_decided",
        "business_id": "artemea",
        "approval_request_id": approval_request_id,
        "ledger_id": decision.record.ledger_id,
        "case_id": case.case_id,
        "action_key": "request_external_action",
        "decision": "approved",
        "approval_state": "approved",
        "execution_state": "pending_execution",
        "actor_ref": "manager token=[REDACTED]",
        "reason": "Approved after call Authorization: [REDACTED]",
        "created_at": "2026-05-31T17:30:00Z",
    }
    assert "raw_decision" not in str(decision)
    [listed_record] = ledger.list_actions(business_id="artemea")
    assert listed_record.approval_state == "approved"
    assert listed_record.execution_state == "pending_execution"


def test_workflow_approval_decision_rejects_cross_business_and_prevents_double_decision(tmp_path):
    _, case = seed_case()
    ledger = SQLiteWorkflowActionLedgerStore(str(tmp_path / "workflow-actions.sqlite3"))
    rule = WorkflowRule(
        rule_id="reject-external-restock",
        business_id="artemea",
        trigger="case_updated",
        conditions=[CaseWorkflowCondition(field="status", value="open")],
        actions=[
            WorkflowAction(
                action_key="request_external_action",
                params={"target": "supplier", "reason": "Request supplier restock"},
            )
        ],
    )
    planned = simulate_case_workflow(rule, case, now=utc(18), action_ledger=ledger, actor_ref="operator:ana")
    approval_request_id = planned["actions"][0]["approval_request_id"]

    with pytest.raises(WorkflowActionLedgerError) as cross_scope:
        ledger.decide_approval_request(
            business_id="other-business",
            approval_request_id=approval_request_id,
            decision="approved",
            actor_ref="manager",
            reason="Cross scope should not see this",
            now=utc(18, 10),
        )

    assert cross_scope.value.code == "approval_request_not_found"

    first_decision = ledger.decide_approval_request(
        business_id="artemea",
        approval_request_id=approval_request_id,
        decision="rejected",
        actor_ref="manager",
        reason="Do not restock",
        now=utc(18, 15),
    )

    assert first_decision.record.approval_state == "rejected"
    assert first_decision.record.execution_state == "failed"
    with pytest.raises(WorkflowActionLedgerError) as second_decision:
        ledger.decide_approval_request(
            business_id="artemea",
            approval_request_id=approval_request_id,
            decision="approved",
            actor_ref="manager",
            reason="Cannot reverse rejected approval token=raw_second_decision_secret",
            now=utc(18, 20),
        )

    assert second_decision.value.code == "approval_request_already_decided"
    assert "raw_second_decision_secret" not in second_decision.value.message


@pytest.mark.parametrize(
    "store_factory",
    [
        lambda tmp_path: InMemoryWorkflowActionLedgerStore(),
        lambda tmp_path: SQLiteWorkflowActionLedgerStore(str(tmp_path / "workflow-actions.sqlite3")),
    ],
)
def test_workflow_approval_queue_projects_only_pending_requests_without_side_effects(tmp_path, store_factory):
    ledger = store_factory(tmp_path)
    later = ledger.record_planned_action(
        business_id="artemea",
        case_id="case-later",
        action_key="request_external_action",
        idempotency_key="workflow/artemea/approval-queue/case-later/request_external_action/later",
        execution_state="blocked_approval_required",
        approval_required=True,
        source="workflow",
        actor_ref="operator token=raw_approval_queue_actor_secret",
        params={
            "target": "supplier-b",
            "reason": "Restock later Authorization: Basic raw_approval_queue_later_secret",
        },
        rule_id="approval-queue",
        now=utc(19),
    )
    earlier = ledger.record_planned_action(
        business_id="artemea",
        case_id="case-earlier",
        action_key="pause_promotion",
        idempotency_key="workflow/artemea/approval-queue/case-earlier/pause_promotion/earlier",
        execution_state="blocked_approval_required",
        approval_required=True,
        source="workflow",
        actor_ref="operator",
        params={
            "target": "campaign-a",
            "reason": "Pause promotion early token=raw_approval_queue_earlier_secret",
        },
        rule_id="approval-queue",
        now=utc(19, 5),
    )
    approved = ledger.record_planned_action(
        business_id="artemea",
        case_id="case-approved",
        action_key="request_external_action",
        idempotency_key="workflow/artemea/approval-queue/case-approved/request_external_action/approved",
        execution_state="blocked_approval_required",
        approval_required=True,
        params={"target": "supplier-c", "reason": "Already approved"},
        rule_id="approval-queue",
        now=utc(19, 10),
    )
    ledger.record_planned_action(
        business_id="other-business",
        case_id="case-other",
        action_key="request_external_action",
        idempotency_key="workflow/other-business/approval-queue/case-other/request_external_action/other",
        execution_state="blocked_approval_required",
        approval_required=True,
        params={"target": "supplier-x", "reason": "Other business"},
        rule_id="approval-queue",
        now=utc(19, 15),
    )
    no_approval = ledger.record_planned_action(
        business_id="artemea",
        case_id="case-no-approval",
        action_key="acknowledge_case",
        idempotency_key="workflow/artemea/approval-queue/case-no-approval/acknowledge_case/no-approval",
        execution_state="dry_run",
        approval_required=False,
        params={"reason": "No approval needed"},
        rule_id="approval-queue",
        now=utc(19, 20),
    )

    assert later.approval_request is not None
    assert earlier.approval_request is not None
    assert approved.approval_request is not None
    assert no_approval.approval_request is None
    ledger.decide_approval_request(
        business_id="artemea",
        approval_request_id=approved.approval_request.approval_request_id,
        decision="approved",
        actor_ref="manager",
        reason="Approved already",
        now=utc(19, 30),
    )

    queue = list_workflow_approval_queue(ledger, business_id="artemea", limit=1)

    assert queue["business_id"] == "artemea"
    assert queue["approval_execution_enabled"] is False
    assert queue["side_effects_executed"] == 0
    assert queue["total"] == 2
    assert queue["returned"] == 1
    assert [request["case_id"] for request in queue["approval_requests"]] == ["case-later"]
    [request] = queue["approval_requests"]
    assert request["status"] == "pending"
    assert request["approval_state"] == "pending"
    assert request["execution_state"] == "blocked_approval_required"
    assert request["approval_request_id"] == later.approval_request.approval_request_id
    assert request["ledger_id"] == later.record.ledger_id
    assert request["action_key"] == "request_external_action"
    assert request["params"]["reason"] == "Restock later Authorization: [REDACTED]"
    assert request["side_effects_executed"] == 0
    assert request["decision_state"] == "pending_human_approval"
    assert "case-earlier" not in str(queue["approval_requests"])
    assert "case-approved" not in str(queue)
    assert "case-other" not in str(queue)
    assert "case-no-approval" not in str(queue)
    assert "raw_approval_queue" not in str(queue)


def test_workflow_approval_queue_rejects_mismatched_ledger_backed_request_metadata():
    record = WorkflowActionLedgerRecord(
        ledger_id="ledger/artemea/mismatch",
        business_id="artemea",
        case_id="case-canonical",
        action_key="request_external_action",
        source="workflow",
        actor_ref="operator",
        idempotency_key="workflow/artemea/mismatch",
        approval_state="pending",
        execution_state="blocked_approval_required",
        params={"target": "supplier-a", "reason": "Restock"},
        rule_id="approval-queue",
        approval_request_id="approval/artemea/mismatch",
        created_at=utc(20),
        updated_at=utc(20),
    )
    mismatched_request = WorkflowApprovalRequest(
        approval_request_id="approval/artemea/mismatch",
        ledger_id=record.ledger_id,
        business_id="artemea",
        case_id="case-forged",
        action_key="pause_promotion",
        requester_ref="operator",
        status="pending",
        requested_at=utc(20),
    )

    class MismatchedLedger(InMemoryWorkflowActionLedgerStore):
        def list_actions(self, *, business_id: str):
            return [record]

        def list_approval_requests(self, *, business_id: str):
            return [mismatched_request]

    queue = list_workflow_approval_queue(MismatchedLedger(), business_id="artemea")

    assert queue["total"] == 0
    assert queue["returned"] == 0
    assert queue["approval_requests"] == []
    assert "case-forged" not in str(queue)
    assert "pause_promotion" not in str(queue)


@pytest.mark.parametrize(
    "store_factory",
    [
        lambda tmp_path: InMemoryWorkflowActionLedgerStore(),
        lambda tmp_path: SQLiteWorkflowActionLedgerStore(str(tmp_path / "workflow-actions.sqlite3")),
    ],
)
def test_workflow_execution_queue_projects_only_approved_pending_actions_without_side_effects(tmp_path, store_factory):
    ledger = store_factory(tmp_path)
    later = ledger.record_planned_action(
        business_id="artemea",
        case_id="case-later",
        action_key="request_external_action",
        idempotency_key="workflow/artemea/execution-queue/case-later/request_external_action/later",
        execution_state="blocked_approval_required",
        approval_required=True,
        source="workflow",
        actor_ref="operator token=raw_queue_actor_secret",
        params={
            "target": "supplier-b",
            "reason": "Restock later",
            "Authorization": "Basic raw_queue_later_secret",
        },
        rule_id="execution-queue",
        now=utc(19),
    )
    earlier = ledger.record_planned_action(
        business_id="artemea",
        case_id="case-earlier",
        action_key="request_external_action",
        idempotency_key="workflow/artemea/execution-queue/case-earlier/request_external_action/earlier",
        execution_state="blocked_approval_required",
        approval_required=True,
        source="workflow",
        actor_ref="operator",
        params={
            "target": "supplier-a",
            "reason": "Restock earlier",
            "Authorization": "Basic raw_queue_earlier_secret",
        },
        rule_id="execution-queue",
        now=utc(19, 5),
    )
    rejected = ledger.record_planned_action(
        business_id="artemea",
        case_id="case-rejected",
        action_key="request_external_action",
        idempotency_key="workflow/artemea/execution-queue/case-rejected/request_external_action/rejected",
        execution_state="blocked_approval_required",
        approval_required=True,
        params={"target": "supplier-c", "reason": "Rejected"},
        rule_id="execution-queue",
        now=utc(19, 10),
    )
    ledger.record_planned_action(
        business_id="other-business",
        case_id="case-other",
        action_key="request_external_action",
        idempotency_key="workflow/other-business/execution-queue/case-other/request_external_action/other",
        execution_state="blocked_approval_required",
        approval_required=True,
        params={"target": "supplier-x", "reason": "Other business"},
        rule_id="execution-queue",
        now=utc(19, 15),
    )
    unknown = ledger.record_planned_action(
        business_id="artemea",
        case_id="case-unknown",
        action_key="invented_llm_action",
        idempotency_key="workflow/artemea/execution-queue/case-unknown/invented_llm_action/unknown",
        execution_state="blocked_approval_required",
        approval_required=True,
        params={"target": "supplier-y", "reason": "Unknown action"},
        rule_id="execution-queue",
        now=utc(19, 20),
    )

    assert later.approval_request is not None
    assert earlier.approval_request is not None
    assert rejected.approval_request is not None
    assert unknown.approval_request is not None
    ledger.decide_approval_request(
        business_id="artemea",
        approval_request_id=later.approval_request.approval_request_id,
        decision="approved",
        actor_ref="manager",
        reason="Approved later",
        now=utc(19, 40),
    )
    ledger.decide_approval_request(
        business_id="artemea",
        approval_request_id=earlier.approval_request.approval_request_id,
        decision="approved",
        actor_ref="manager",
        reason="Approved earlier",
        now=utc(19, 30),
    )
    ledger.decide_approval_request(
        business_id="artemea",
        approval_request_id=rejected.approval_request.approval_request_id,
        decision="rejected",
        actor_ref="manager",
        reason="Do not execute",
        now=utc(19, 35),
    )
    ledger.decide_approval_request(
        business_id="artemea",
        approval_request_id=unknown.approval_request.approval_request_id,
        decision="approved",
        actor_ref="manager",
        reason="Unknown actions must remain outside execution queue",
        now=utc(19, 45),
    )

    queue = list_workflow_execution_queue(ledger, business_id="artemea")

    assert queue["business_id"] == "artemea"
    assert queue["execution_enabled"] is False
    assert queue["side_effects_executed"] == 0
    assert queue["total"] == 2
    assert [action["case_id"] for action in queue["actions"]] == ["case-earlier", "case-later"]
    assert [action["mode"] for action in queue["actions"]] == ["approval_required", "approval_required"]
    assert [action["side_effect"] for action in queue["actions"]] == ["external", "external"]
    assert [action["requires_approval"] for action in queue["actions"]] == [True, True]
    assert [action["execution_state"] for action in queue["actions"]] == ["pending_execution", "pending_execution"]
    assert [action["approval_state"] for action in queue["actions"]] == ["approved", "approved"]
    assert queue["actions"][0]["params"]["Authorization"] == "[REDACTED]"
    assert queue["actions"][0]["side_effects_executed"] == 0
    assert queue["actions"][0]["executor_state"] == "not_implemented"
    assert "case-rejected" not in str(queue)
    assert "case-other" not in str(queue)
    assert "case-unknown" not in str(queue)
    assert "invented_llm_action" not in str(queue)
    assert "raw_queue" not in str(queue)


@pytest.mark.parametrize(
    "store_factory",
    [
        lambda tmp_path: InMemoryWorkflowActionLedgerStore(),
        lambda tmp_path: SQLiteWorkflowActionLedgerStore(str(tmp_path / "workflow-actions.sqlite3")),
    ],
)
def test_workflow_action_audit_events_project_planning_approval_and_decision_without_side_effects(
    tmp_path, store_factory
):
    ledger = store_factory(tmp_path)
    ledger.record_planned_action(
        business_id="artemea",
        case_id="case-dry-run",
        action_key="acknowledge_case",
        idempotency_key="workflow/artemea/audit/case-dry-run/acknowledge_case/dry-run",
        execution_state="dry_run",
        approval_required=False,
        source="workflow",
        actor_ref="operator token=raw_audit_actor_secret",
        params={"reason": "Ack token=raw_audit_dry_param_secret"},
        rule_id="audit-rule",
        now=utc(21),
    )
    approval_write = ledger.record_planned_action(
        business_id="artemea",
        case_id="case-approval",
        action_key="request_external_action",
        idempotency_key="workflow/artemea/audit/case-approval/request_external_action/approval",
        execution_state="blocked_approval_required",
        approval_required=True,
        source="workflow",
        actor_ref="operator",
        params={
            "target": "supplier-a",
            "reason": "Restock Authorization: Basic raw_audit_plan_secret",
        },
        rule_id="audit-rule",
        now=utc(21, 5),
    )
    ledger.record_planned_action(
        business_id="other-business",
        case_id="case-other",
        action_key="request_external_action",
        idempotency_key="workflow/other-business/audit/case-other/request_external_action/other",
        execution_state="blocked_approval_required",
        approval_required=True,
        params={"target": "supplier-x", "reason": "Other business"},
        rule_id="audit-rule",
        now=utc(21, 10),
    )
    assert approval_write.approval_request is not None
    ledger.decide_approval_request(
        business_id="artemea",
        approval_request_id=approval_write.approval_request.approval_request_id,
        decision="approved",
        actor_ref="manager token=raw_audit_decision_actor_secret",
        reason="Approved Authorization: Basic raw_audit_decision_reason_secret",
        now=utc(21, 30),
    )

    audit = list_workflow_action_audit_events(ledger, business_id="artemea", limit=3)

    assert audit["business_id"] == "artemea"
    assert audit["audit_projection_enabled"] is True
    assert audit["side_effects_executed"] == 0
    assert audit["total"] == 4
    assert audit["returned"] == 3
    assert [event["event_type"] for event in audit["events"]] == [
        "workflow_action_planned",
        "workflow_action_planned",
        "workflow_approval_requested",
    ]
    assert audit["events"][0]["actor_ref"] == "operator token=[REDACTED]"
    assert audit["events"][0]["approval_state"] == "not_required"
    assert audit["events"][0]["execution_state"] == "dry_run"
    assert audit["events"][1]["approval_request_id"] == approval_write.approval_request.approval_request_id
    assert audit["events"][1]["params"]["reason"] == "Restock Authorization: [REDACTED]"
    assert audit["events"][2]["status"] == "pending"
    assert audit["events"][2]["current_status"] == "approved"
    assert audit["events"][2]["decision_state"] == "approval_requested"
    assert audit["events"][2]["approval_state"] == "pending"
    assert audit["events"][2]["current_approval_state"] == "approved"
    assert audit["events"][2]["execution_state"] == "blocked_approval_required"
    assert audit["events"][2]["current_execution_state"] == "pending_execution"

    full_audit = list_workflow_action_audit_events(ledger, business_id="artemea")
    assert [event["event_type"] for event in full_audit["events"]] == [
        "workflow_action_planned",
        "workflow_action_planned",
        "workflow_approval_requested",
        "workflow_approval_decided",
    ]
    decision_event = full_audit["events"][-1]
    assert decision_event["decision"] == "approved"
    assert decision_event["decision_actor_ref"] == "manager token=[REDACTED]"
    assert decision_event["decision_reason"] == "Approved Authorization: [REDACTED]"
    assert decision_event["approval_state"] == "approved"
    assert decision_event["execution_state"] == "pending_execution"
    assert "case-other" not in str(full_audit)
    assert "other-business" not in str(full_audit)
    assert "raw_audit" not in str(audit)
    assert "raw_audit" not in str(full_audit)

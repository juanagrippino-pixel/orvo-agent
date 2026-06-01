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
                params={"target": "supplier", "Authorization": "Basic raw_external_secret"},
            )
        ],
    )

    result = simulate_case_workflow(rule, case, now=utc(10))

    planned_action = result["actions"][0]
    assert planned_action["action_key"] == "request_external_action"
    assert planned_action["mode"] == "approval_required"
    assert planned_action["requires_approval"] is True
    assert planned_action["execution_status"] == "blocked_approval_required"
    assert planned_action["side_effect"] == "external"
    assert "raw_external_secret" not in str(result)
    assert planned_action["params"]["Authorization"] == "[REDACTED]"


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
    assert result["side_effects_executed"] == 0


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

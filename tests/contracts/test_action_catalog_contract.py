"""Contract tests for the canonical case action catalog.

The action catalog is the source of truth for operator/workflow projections.
These tests guard the current safe-by-default boundary: registered actions that
would cause external side effects may exist for planning/approval modeling, but
must not become API-executable until a governed executor with audit/idempotency
exists.
"""

from __future__ import annotations

import pytest

from app.brain.action_catalog import ACTION_CATALOG, API_ENABLED_CASE_ACTION_KEYS, workflow_action_registry
from app.brain.workflow_action_key_validation import validate_workflow_action_key_filter
from app.brain.workflow_action_ledger import WorkflowActionLedgerError


def test_external_side_effect_actions_remain_approval_gated_and_api_disabled():
    external_actions = [
        definition
        for definition in ACTION_CATALOG.values()
        if definition.side_effect == "external"
    ]

    assert external_actions, "catalog must keep explicit external-action entries visible for review"
    assert all(definition.mode == "approval_required" for definition in external_actions)
    assert all(definition.requires_approval for definition in external_actions)
    assert all(not definition.api_enabled for definition in external_actions)
    assert {definition.action_key for definition in external_actions}.isdisjoint(API_ENABLED_CASE_ACTION_KEYS)
    assert all(
        definition.operator_projection(can_execute_case_actions=True)["operator_executable"] is False
        for definition in external_actions
    )


def test_workflow_action_registry_and_approval_filter_share_catalog_truth():
    assert workflow_action_registry() == ACTION_CATALOG

    approval_required_action_keys = {
        action_key
        for action_key, definition in ACTION_CATALOG.items()
        if definition.mode == "approval_required" and definition.requires_approval
    }

    validate_workflow_action_key_filter(None, require_approval_required=True)
    for action_key, definition in ACTION_CATALOG.items():
        if action_key in approval_required_action_keys:
            validate_workflow_action_key_filter(action_key, require_approval_required=True)
            continue

        with pytest.raises(WorkflowActionLedgerError):
            validate_workflow_action_key_filter(action_key, require_approval_required=True)

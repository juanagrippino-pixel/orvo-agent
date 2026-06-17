"""Contract tests for the canonical case action catalog.

The action catalog is the source of truth for operator/workflow projections.
These tests guard the current safe-by-default boundary: registered actions that
would cause external side effects may exist for planning/approval modeling, but
must not become API-executable until a governed executor with audit/idempotency
exists.
"""

from __future__ import annotations

from app.brain.action_catalog import ACTION_CATALOG, API_ENABLED_CASE_ACTION_KEYS


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



def test_owner_facing_case_families_always_have_catalog_backed_non_external_next_steps():
    """Promoted owner-facing cases must retain at least one safe registered action.

    WhatsApp/operator owner surfaces are allowed to project catalog action keys,
    but they must not promote a case family whose only next step is an external,
    approval-gated write. This contract catches catalog drift when a case family
    becomes owner-facing or action metadata changes.
    """

    from app.brain.operational_cases import OWNER_FACING_OPERATIONAL_CASE_TYPES

    actions_by_family = {
        case_family: [
            definition
            for definition in ACTION_CATALOG.values()
            if case_family in definition.case_families
        ]
        for case_family in OWNER_FACING_OPERATIONAL_CASE_TYPES
    }

    missing_families = sorted(
        case_family for case_family, definitions in actions_by_family.items() if not definitions
    )
    families_with_only_external_actions = sorted(
        case_family
        for case_family, definitions in actions_by_family.items()
        if not any(definition.side_effect != "external" for definition in definitions)
    )

    assert missing_families == []
    assert families_with_only_external_actions == []

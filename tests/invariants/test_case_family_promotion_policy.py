"""Invariant tests for case-family promotion boundaries.

Owner-facing projections must only expose families that are deliberately promoted
through the semantic registry. Deferred/internal families can remain in product
catalog docs, but should not become owner-facing just because a detector or
legacy literal exists in code.
"""


def test_owner_facing_case_families_are_explicitly_promoted_not_just_metric_registered():
    from app.brain.operational_cases import (
        DETECTABLE_OPERATIONAL_CASE_TYPES,
        OWNER_FACING_OPERATIONAL_CASE_TYPES,
    )
    from app.brain.semantics import CASE_FAMILY_METRICS
    from app.brain.work_items import operational_case_issue_type_definitions

    registered_case_families = set(CASE_FAMILY_METRICS)
    expected_promoted_owner_facing = {"sales_drop", "stockout_risk", "data_stale"}
    expected_readiness_gated = {
        "fulfillment_backlog",
        "spend_without_orders",
        "unanswered_conversations",
    }
    issue_types_by_case_type = {
        definition["case_type"]: definition for definition in operational_case_issue_type_definitions()
    }

    assert DETECTABLE_OPERATIONAL_CASE_TYPES == registered_case_families
    assert OWNER_FACING_OPERATIONAL_CASE_TYPES == expected_promoted_owner_facing
    assert OWNER_FACING_OPERATIONAL_CASE_TYPES <= DETECTABLE_OPERATIONAL_CASE_TYPES
    assert expected_readiness_gated <= registered_case_families
    assert expected_readiness_gated.isdisjoint(OWNER_FACING_OPERATIONAL_CASE_TYPES)
    assert "channel_mix_shift" not in registered_case_families
    assert "channel_mix_shift" not in OWNER_FACING_OPERATIONAL_CASE_TYPES
    assert issue_types_by_case_type["channel_mix_shift"]["release_state"] == "deferred"
    assert {
        case_type
        for case_type, definition in issue_types_by_case_type.items()
        if definition["release_state"] == "promoted"
    } == expected_promoted_owner_facing
    assert {
        case_type
        for case_type, definition in issue_types_by_case_type.items()
        if definition["release_state"] == "readiness_gated"
    } == expected_readiness_gated

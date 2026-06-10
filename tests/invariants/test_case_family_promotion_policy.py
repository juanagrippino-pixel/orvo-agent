"""Invariant tests for case-family promotion boundaries.

Owner-facing projections must only expose families that are deliberately promoted
through the semantic registry. Deferred/internal families can remain in product
catalog docs, but should not become owner-facing just because a detector or
legacy literal exists in code.
"""


def test_owner_facing_case_families_are_registry_promoted_and_channel_mix_shift_stays_deferred():
    from app.brain.operational_cases import (
        DETECTABLE_OPERATIONAL_CASE_TYPES,
        OWNER_FACING_OPERATIONAL_CASE_TYPES,
    )
    from app.brain.semantics import CASE_FAMILY_METRICS
    from app.brain.work_items import operational_case_issue_type_definitions

    registered_case_families = set(CASE_FAMILY_METRICS)
    issue_types_by_case_type = {
        definition["case_type"]: definition for definition in operational_case_issue_type_definitions()
    }

    assert OWNER_FACING_OPERATIONAL_CASE_TYPES <= DETECTABLE_OPERATIONAL_CASE_TYPES
    assert OWNER_FACING_OPERATIONAL_CASE_TYPES == registered_case_families
    assert DETECTABLE_OPERATIONAL_CASE_TYPES == registered_case_families
    assert "channel_mix_shift" not in registered_case_families
    assert "channel_mix_shift" not in OWNER_FACING_OPERATIONAL_CASE_TYPES
    assert issue_types_by_case_type["channel_mix_shift"]["release_state"] == "deferred"
    assert {
        case_type
        for case_type, definition in issue_types_by_case_type.items()
        if definition["release_state"] == "promoted"
    } == registered_case_families

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

    registered_case_families = set(CASE_FAMILY_METRICS)

    assert OWNER_FACING_OPERATIONAL_CASE_TYPES <= DETECTABLE_OPERATIONAL_CASE_TYPES
    assert OWNER_FACING_OPERATIONAL_CASE_TYPES == registered_case_families
    assert DETECTABLE_OPERATIONAL_CASE_TYPES == registered_case_families
    assert "channel_mix_shift" not in registered_case_families
    assert "channel_mix_shift" not in OWNER_FACING_OPERATIONAL_CASE_TYPES

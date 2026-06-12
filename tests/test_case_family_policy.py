"""Tests for the explicit case-family readiness/promotion policy registry."""

from typing import get_args

from app.brain.case_family_policy import (
    CASE_FAMILY_READINESS_POLICY,
    case_family_release_state,
    detectable_case_families,
    owner_facing_case_families,
    readiness_gated_case_families,
)
from app.brain.operational_cases import OperationalCaseType
from app.brain.semantics import CASE_FAMILY_METRICS
from app.brain.work_items import operational_case_issue_type_definitions


EXPECTED_PROMOTED_OWNER_FACING = {"sales_drop", "stockout_risk", "data_stale"}
EXPECTED_READINESS_GATED = {
    "fulfillment_backlog",
    "spend_without_orders",
    "unanswered_conversations",
}
DEFERRED_CASE_TYPES = {"channel_mix_shift"}


def test_case_family_policy_is_the_single_source_for_release_state():
    assert CASE_FAMILY_READINESS_POLICY.promoted_owner_facing == EXPECTED_PROMOTED_OWNER_FACING
    assert detectable_case_families() == frozenset(CASE_FAMILY_METRICS)
    assert owner_facing_case_families() == EXPECTED_PROMOTED_OWNER_FACING
    assert readiness_gated_case_families() == EXPECTED_READINESS_GATED
    assert EXPECTED_PROMOTED_OWNER_FACING <= detectable_case_families()
    assert EXPECTED_READINESS_GATED == detectable_case_families() - EXPECTED_PROMOTED_OWNER_FACING
    assert CASE_FAMILY_READINESS_POLICY.deferred == DEFERRED_CASE_TYPES

    assert case_family_release_state("sales_drop") == "promoted"
    assert case_family_release_state("unanswered_conversations") == "readiness_gated"
    assert case_family_release_state("channel_mix_shift") == "deferred"
    assert case_family_release_state("unknown_internal") == "internal_only"

    definitions = {
        definition["case_type"]: definition
        for definition in operational_case_issue_type_definitions()
    }
    for case_type in get_args(OperationalCaseType):
        assert definitions[case_type]["release_state"] == case_family_release_state(case_type)

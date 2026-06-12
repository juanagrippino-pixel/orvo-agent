"""Explicit readiness/promotion policy for D2C Operational Case families.

The semantic metric registry proves that a family has evidence-bearing metrics.
This policy adds the product-release gate used by Operational Case and WorkItem
projections: only deliberately promoted families are owner-facing, while other
registered families remain readiness-gated until their connector, stale-source,
dedupe, action, and projection gates are implemented and tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping

from app.brain.semantics.metric_registry import CASE_FAMILY_METRICS

CaseFamilyReleaseState = Literal["promoted", "readiness_gated", "deferred", "internal_only"]

_PROMOTED_OWNER_FACING_CASE_FAMILIES: frozenset[str] = frozenset(
    {
        "sales_drop",
        "stockout_risk",
        "data_stale",
    }
)
_DEFERRED_CASE_FAMILIES: frozenset[str] = frozenset({"channel_mix_shift"})


@dataclass(frozen=True, slots=True)
class CaseFamilyReadinessPolicy:
    """Canonical release/readiness policy for Operational Case families."""

    detected_case_families: frozenset[str]
    promoted_owner_facing: frozenset[str]
    deferred: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.promoted_owner_facing <= self.detected_case_families:
            raise ValueError("promoted owner-facing case families must be registered as detectable")
        if self.deferred & self.detected_case_families:
            overlap = sorted(self.deferred & self.detected_case_families)
            raise ValueError(f"deferred case families must not be detectable yet: {overlap}")

    @property
    def readiness_gated(self) -> frozenset[str]:
        """Registered case families that are not yet owner-facing."""

        return frozenset(self.detected_case_families - self.promoted_owner_facing)

    @property
    def declared_case_families(self) -> frozenset[str]:
        """All case families known to this policy, including deferred catalog items."""

        return frozenset(self.detected_case_families | self.deferred)

    def release_state(self, case_type: str) -> CaseFamilyReleaseState:
        """Return the release state for a case-family identifier."""

        if case_type in self.promoted_owner_facing:
            return "promoted"
        if case_type in self.detected_case_families:
            return "readiness_gated"
        if case_type in self.deferred:
            return "deferred"
        return "internal_only"


CASE_FAMILY_READINESS_POLICY: CaseFamilyReadinessPolicy = CaseFamilyReadinessPolicy(
    detected_case_families=frozenset(CASE_FAMILY_METRICS),
    promoted_owner_facing=_PROMOTED_OWNER_FACING_CASE_FAMILIES,
    deferred=_DEFERRED_CASE_FAMILIES,
)

CASE_FAMILY_METRIC_KEYS: Mapping[str, tuple[str, ...]] = CASE_FAMILY_METRICS

DETECTABLE_CASE_FAMILIES: frozenset[str] = CASE_FAMILY_READINESS_POLICY.detected_case_families
OWNER_FACING_CASE_FAMILIES: frozenset[str] = CASE_FAMILY_READINESS_POLICY.promoted_owner_facing
READINESS_GATED_CASE_FAMILIES: frozenset[str] = CASE_FAMILY_READINESS_POLICY.readiness_gated
DEFERRED_CASE_FAMILIES: frozenset[str] = CASE_FAMILY_READINESS_POLICY.deferred

# Backward-compatible, read-only mapping for callers that still inspect policy as data.
CASE_FAMILY_READINESS_STATES: Mapping[str, CaseFamilyReleaseState] = MappingProxyType(
    {
        case_type: CASE_FAMILY_READINESS_POLICY.release_state(case_type)
        for case_type in sorted(CASE_FAMILY_READINESS_POLICY.declared_case_families)
    }
)


def detectable_case_families() -> frozenset[str]:
    """Return case families with registered metric evidence contracts."""

    return DETECTABLE_CASE_FAMILIES


def owner_facing_case_families() -> frozenset[str]:
    """Return case families deliberately promoted for owner-facing projections."""

    return OWNER_FACING_CASE_FAMILIES


def readiness_gated_case_families() -> frozenset[str]:
    """Return registered case families that are not yet owner-facing."""

    return READINESS_GATED_CASE_FAMILIES


def case_family_release_state(case_type: str) -> CaseFamilyReleaseState:
    """Return the release/readiness state for a case-family identifier."""

    return CASE_FAMILY_READINESS_POLICY.release_state(case_type)


def case_family_metric_keys(case_type: str) -> tuple[str, ...]:
    """Return registered semantic metric keys for a case family."""

    return CASE_FAMILY_METRIC_KEYS.get(case_type, ())


__all__ = [
    "CASE_FAMILY_METRIC_KEYS",
    "CASE_FAMILY_READINESS_POLICY",
    "CASE_FAMILY_READINESS_STATES",
    "CaseFamilyReadinessPolicy",
    "CaseFamilyReleaseState",
    "DEFERRED_CASE_FAMILIES",
    "DETECTABLE_CASE_FAMILIES",
    "OWNER_FACING_CASE_FAMILIES",
    "READINESS_GATED_CASE_FAMILIES",
    "case_family_metric_keys",
    "case_family_release_state",
    "detectable_case_families",
    "owner_facing_case_families",
    "readiness_gated_case_families",
]

"""Explicit readiness/promotion policy for D2C Operational Case families.

The semantic metric registry proves that a family has evidence-bearing metrics.
This policy adds the product-release gate used by Operational Case and WorkItem
projections: only deliberately promoted families are owner-facing, while other
registered families remain readiness-gated until their connector, stale-source,
dedupe, action, projection, and redaction gates are implemented and tested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
_PROMOTION_PREREQUISITES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "sales_drop": (
            "metric_registry",
            "evidence_snapshots",
            "owner_projection",
            "operator_actions",
        ),
        "stockout_risk": (
            "metric_registry",
            "inventory_source",
            "evidence_snapshots",
            "owner_projection",
            "operator_actions",
        ),
        "data_stale": (
            "connector_failure_detection",
            "metric_registry",
            "evidence_snapshots",
            "owner_projection",
            "operator_actions",
        ),
        "spend_without_orders": (
            "metric_registry",
            "ads_source",
            "dedupe_contract",
            "owner_projection",
            "operator_actions",
        ),
        "fulfillment_backlog": (
            "metric_registry",
            "fulfillment_source",
            "dedupe_contract",
            "owner_projection",
            "operator_actions",
        ),
        "unanswered_conversations": (
            "metric_registry",
            "support_source",
            "business_hours_policy",
            "redaction_pii_gate",
            "owner_projection",
            "operator_actions",
        ),
        "channel_mix_shift": (
            "channel_attribution_metrics",
            "dedupe_contract",
            "owner_projection",
            "operator_actions",
        ),
    }
)


@dataclass(frozen=True, slots=True)
class CaseFamilyReadinessPolicy:
    """Canonical release/readiness policy for Operational Case families."""

    detected_case_families: frozenset[str]
    promoted_owner_facing: frozenset[str]
    deferred: frozenset[str] = frozenset()
    promotion_prerequisites: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: _PROMOTION_PREREQUISITES
    )

    def __post_init__(self) -> None:
        known_case_families = self.detected_case_families | self.deferred
        extra_prerequisites = sorted(set(self.promotion_prerequisites) - known_case_families)
        if extra_prerequisites:
            raise ValueError(
                "promotion prerequisites declared for unknown case families: "
                f"{extra_prerequisites}"
            )
        if not self.promoted_owner_facing <= self.detected_case_families:
            raise ValueError("promoted owner-facing case families must be registered as detectable")
        if self.deferred & self.detected_case_families:
            overlap = sorted(self.deferred & self.detected_case_families)
            raise ValueError(f"deferred case families must not be detectable yet: {overlap}")
        missing_prerequisites = sorted(known_case_families - set(self.promotion_prerequisites))
        if missing_prerequisites:
            raise ValueError(f"case-family promotion prerequisites missing for: {missing_prerequisites}")

    @property
    def readiness_gated(self) -> frozenset[str]:
        """Registered case families that are not yet owner-facing."""

        return frozenset(self.detected_case_families - self.promoted_owner_facing)

    @property
    def declared_case_families(self) -> frozenset[str]:
        """All case families known to this policy, including deferred catalog items."""

        return frozenset(self.detected_case_families | self.deferred)

    def release_state(self, case_type: str) -> CaseFamilyReleaseState:
        """Return the release/readiness state for a case-family identifier."""

        if case_type in self.promoted_owner_facing:
            return "promoted"
        if case_type in self.detected_case_families:
            return "readiness_gated"
        if case_type in self.deferred:
            return "deferred"
        return "internal_only"

    def promotion_prerequisites_for(self, case_type: str) -> tuple[str, ...]:
        """Return explicit prerequisites needed before owner-facing promotion."""

        return self.promotion_prerequisites.get(case_type, ())


CASE_FAMILY_READINESS_POLICY: CaseFamilyReadinessPolicy = CaseFamilyReadinessPolicy(
    detected_case_families=frozenset(CASE_FAMILY_METRICS),
    promoted_owner_facing=_PROMOTED_OWNER_FACING_CASE_FAMILIES,
    deferred=_DEFERRED_CASE_FAMILIES,
    promotion_prerequisites=_PROMOTION_PREREQUISITES,
)

CASE_FAMILY_METRIC_KEYS: Mapping[str, tuple[str, ...]] = CASE_FAMILY_METRICS

DETECTABLE_CASE_FAMILIES: frozenset[str] = CASE_FAMILY_READINESS_POLICY.detected_case_families
OWNER_FACING_CASE_FAMILIES: frozenset[str] = CASE_FAMILY_READINESS_POLICY.promoted_owner_facing
READINESS_GATED_CASE_FAMILIES: frozenset[str] = CASE_FAMILY_READINESS_POLICY.readiness_gated
DEFERRED_CASE_FAMILIES: frozenset[str] = CASE_FAMILY_READINESS_POLICY.deferred

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


def deferred_case_families() -> frozenset[str]:
    """Return case families intentionally kept out of detection until promoted."""

    return DEFERRED_CASE_FAMILIES


def case_family_promotion_prerequisites(case_type: str) -> tuple[str, ...]:
    """Return prerequisites for promoting a case family into owner-facing use."""

    return CASE_FAMILY_READINESS_POLICY.promotion_prerequisites_for(case_type)


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
    "case_family_promotion_prerequisites",
    "case_family_release_state",
    "deferred_case_families",
    "detectable_case_families",
    "owner_facing_case_families",
    "readiness_gated_case_families",
]

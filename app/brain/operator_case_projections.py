"""Shared Operational Case projection helpers for operator surfaces.

These helpers keep read-only operator APIs, JQL-lite filters, and dashboard
summaries aligned on derived case projection fields without making those
surfaces a source of truth.
"""

from __future__ import annotations

from datetime import datetime

from app.brain.operational_cases import OperationalCase

EVIDENCE_FRESHNESS_STATES = frozenset({"fresh", "stale", "degraded", "missing", "unknown"})
_DEGRADED_FRESHNESS_STATES = frozenset({"stale", "degraded", "missing"})


def latest_evidence_at(case: OperationalCase) -> datetime | None:
    if not case.evidence_snapshots:
        return None
    return max(snapshot.captured_at for snapshot in case.evidence_snapshots)


def source_connectors(case: OperationalCase) -> list[str]:
    return sorted({snapshot.source for snapshot in case.evidence_snapshots if snapshot.source})


def evidence_freshness_states(case: OperationalCase) -> list[str]:
    """Return canonical evidence freshness states present on a case."""

    return sorted({snapshot.freshness_state for snapshot in case.evidence_snapshots if snapshot.freshness_state})


def entity_kind(case: OperationalCase) -> str:
    """Return the canonical entity kind bucket used by operator projections."""

    kind = case.entity_scope.get("kind")
    if not isinstance(kind, str):
        return "unknown"
    normalized = kind.strip()
    return normalized or "unknown"


def is_case_degraded(case: OperationalCase) -> bool:
    return any(snapshot.freshness_state in _DEGRADED_FRESHNESS_STATES for snapshot in case.evidence_snapshots)

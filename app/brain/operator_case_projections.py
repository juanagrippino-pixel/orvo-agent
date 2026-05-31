"""Shared Operational Case projection helpers for operator surfaces.

These helpers keep read-only operator APIs, JQL-lite filters, and dashboard
summaries aligned on derived case projection fields without making those
surfaces a source of truth.
"""

from __future__ import annotations

from datetime import datetime

from app.brain.operational_cases import OperationalCase

_DEGRADED_FRESHNESS_STATES = frozenset({"stale", "degraded", "missing"})


def latest_evidence_at(case: OperationalCase) -> datetime | None:
    if not case.evidence_snapshots:
        return None
    return max(snapshot.captured_at for snapshot in case.evidence_snapshots)


def source_connectors(case: OperationalCase) -> list[str]:
    return sorted({snapshot.source for snapshot in case.evidence_snapshots if snapshot.source})


def is_case_degraded(case: OperationalCase) -> bool:
    return any(snapshot.freshness_state in _DEGRADED_FRESHNESS_STATES for snapshot in case.evidence_snapshots)

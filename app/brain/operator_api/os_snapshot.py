"""OS snapshot projection for the operator home surface (Milestone 4C).

A deterministic, tenant-scoped, read-only projection over Operational Cases,
the run ledger, and registry promotion state. It renders module health, the
case queue summary, the next obvious action, and readiness lanes — it never
computes metrics, creates cases, or mutates lifecycle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.brain.operational_cases import (
    DETECTABLE_OPERATIONAL_CASE_TYPES,
    OWNER_FACING_OPERATIONAL_CASE_TYPES,
    OperationalCase,
    OperationalCaseStore,
)
from app.brain.run_ledger import RunLedger
from app.brain.security.redaction import redact_secrets

from .cases import case_queue_item, summarize_case_queue
from .common import _ACTIONABLE_STATUSES, OperatorAPIError, _iso, _is_degraded
from .projections import _case_suggested_action_keys, run_history_item

_DATA_TRUTH_CASE_FAMILY = "data_stale"

# Console-order module lanes per the D2C roadmap (Milestone 4C) and the
# OS snapshot UX brief. ``data_stale`` is cross-cutting data truth and is
# intentionally not a module backlog.
_OS_MODULE_DEFINITIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("sales_orders", "Ventas", ("sales_drop", "spend_without_orders", "channel_mix_shift")),
    ("stock_fulfillment", "Stock y entregas", ("stockout_risk", "fulfillment_backlog")),
    ("customer_attention", "Atención a clientes", ("unanswered_conversations",)),
    ("arca_fiscal", "ARCA / Facturación", ()),
    ("treasury_reporting", "Caja y reportes", ()),
)

# Deterministic lifecycle progression mirrored from the registered case
# transition table; keys are registered catalog actions with status effects.
_LIFECYCLE_NEXT_ACTION_KEYS: dict[str, str] = {
    "open": "acknowledge_case",
    "acknowledged": "mark_in_progress",
    "in_progress": "resolve_case",
}


def _module_lane(case_families: tuple[str, ...]) -> str:
    if any(family in OWNER_FACING_OPERATIONAL_CASE_TYPES for family in case_families):
        return "automated"
    if any(family in DETECTABLE_OPERATIONAL_CASE_TYPES for family in case_families):
        return "readiness_gated"
    return "readiness_lane"


def _module_status(lane: str, actionable_cases: int) -> str:
    if lane == "readiness_lane":
        return "not_connected"
    if lane == "readiness_gated":
        return "setup_required"
    return "attention" if actionable_cases > 0 else "ok"


def _next_action_projection(top_case: OperationalCase | None) -> dict[str, Any]:
    if top_case is None:
        return {
            "kind": "all_clear",
            "case": None,
            "suggested_action_keys": [],
            "lifecycle_action_key": None,
        }
    return {
        "kind": "work_case",
        "case": case_queue_item(top_case),
        "suggested_action_keys": _case_suggested_action_keys(top_case),
        "lifecycle_action_key": _LIFECYCLE_NEXT_ACTION_KEYS.get(top_case.status),
    }


def get_os_snapshot(
    store: OperationalCaseStore,
    ledger: RunLedger,
    *,
    business_id: str,
    now: datetime,
) -> dict[str, Any]:
    """Project the operator-home OS snapshot for one business.

    Returns module health lanes, cross-cutting data health, the case queue
    summary, the single highest-priority next action with registered action
    keys only, and latest-run runtime health.
    """

    if now.tzinfo is None or now.utcoffset() is None:
        raise OperatorAPIError("invalid_now", "now must be timezone-aware", status_code=400)
    reference = now.astimezone(timezone.utc)

    family_to_module: dict[str, str] = {
        family: module_key
        for module_key, _label, families in _OS_MODULE_DEFINITIONS
        for family in families
    }
    actionable_by_module: dict[str, int] = {}
    critical_by_module: dict[str, int] = {}
    degraded_by_module: dict[str, int] = {}
    data_truth_actionable = 0
    top_case: OperationalCase | None = None

    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        if top_case is None or (-case.priority_score, case.case_id) < (
            -top_case.priority_score,
            top_case.case_id,
        ):
            top_case = case
        if case.case_type == _DATA_TRUTH_CASE_FAMILY:
            data_truth_actionable += 1
            continue
        module_key = family_to_module.get(case.case_type)
        if module_key is None:
            continue
        actionable_by_module[module_key] = actionable_by_module.get(module_key, 0) + 1
        if case.severity == "critical":
            critical_by_module[module_key] = critical_by_module.get(module_key, 0) + 1
        if _is_degraded(case):
            degraded_by_module[module_key] = degraded_by_module.get(module_key, 0) + 1

    modules: list[dict[str, Any]] = []
    for module_key, label, families in _OS_MODULE_DEFINITIONS:
        lane = _module_lane(families)
        actionable_cases = actionable_by_module.get(module_key, 0)
        modules.append(
            {
                "module_key": module_key,
                "label": label,
                "lane": lane,
                "status": _module_status(lane, actionable_cases),
                "case_families": list(families),
                "owner_facing_case_families": [
                    family for family in families if family in OWNER_FACING_OPERATIONAL_CASE_TYPES
                ],
                "actionable_cases": actionable_cases,
                "actionable_critical": critical_by_module.get(module_key, 0),
                "degraded_cases": degraded_by_module.get(module_key, 0),
            }
        )

    runs = ledger.list_runs(business_id=business_id, limit=1)
    latest_run = runs[0] if runs else None

    return redact_secrets(
        {
            "business_id": business_id,
            "now": _iso(reference),
            "modules": modules,
            "data_health": {
                "case_family": _DATA_TRUTH_CASE_FAMILY,
                "actionable_cases": data_truth_actionable,
                "status": "attention" if data_truth_actionable > 0 else "ok",
            },
            "case_queue_summary": summarize_case_queue(store, business_id=business_id),
            "next_action": _next_action_projection(top_case),
            "runtime_health": {
                "latest_run": run_history_item(latest_run) if latest_run is not None else None,
                "latest_run_status": latest_run.status if latest_run is not None else None,
            },
        }
    )


__all__ = [name for name in globals() if not name.startswith("__")]

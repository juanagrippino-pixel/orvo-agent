from __future__ import annotations

from datetime import date
from typing import Any

from app.brain.action_catalog import ACTION_CATALOG
from app.brain.operational_cases import (
    ACTIONABLE_OPERATIONAL_CASE_STATUSES,
    OperationalCase,
    OperationalCaseStore,
)
from app.brain.reporting import compose_owner_case_brief, order_owner_case_brief_cases
from app.brain.security.redaction import redact_secrets, redact_text

from .common import (
    OperatorAPIError,
    _source_connectors,
    _worst_freshness_state,
    parse_limit,
)
from .projections import _case_suggested_action_keys, _case_suggested_actions


def _parse_report_date(value: str | None) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise OperatorAPIError("invalid_report_date", "report_date must be YYYY-MM-DD", status_code=400) from exc


def _owner_brief_cases(store: OperationalCaseStore, business_id: str) -> list[OperationalCase]:
    cases: list[OperationalCase] = []
    for status in ACTIONABLE_OPERATIONAL_CASE_STATUSES:
        cases.extend(store.list_cases(business_id=business_id, status=status, limit=None))
    return order_owner_case_brief_cases(cases)


def _freshness_counts(cases: list[OperationalCase]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        state = _worst_freshness_state(case) or "missing"
        counts[state] = counts.get(state, 0) + 1
    return counts


def _owner_brief_evidence_freshness(
    *,
    visible: list[OperationalCase],
    actionable: list[OperationalCase],
) -> dict[str, Any]:
    total = _freshness_counts(actionable)
    return {
        "displayed": _freshness_counts(visible),
        "total_actionable": total,
        "has_degraded_or_stale_evidence": any(state in {"degraded", "stale", "missing"} for state in total),
    }


def _owner_brief_displayed_cases(cases: list[OperationalCase]) -> list[dict[str, Any]]:
    """Return whitelisted action context for cases shown in owner brief text."""

    return [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "source_connectors": _source_connectors(case),
            "evidence_snapshot_ids": _owner_brief_evidence_snapshot_ids(case),
            "suggested_action_keys": _case_suggested_action_keys(case),
            "suggested_actions": _case_suggested_actions(case),
        }
        for case in cases
    ]


def _owner_brief_evidence_snapshot_ids(case: OperationalCase) -> list[str]:
    snapshot_ids: list[str] = []
    for snapshot in case.evidence_snapshots:
        if snapshot.snapshot_id and snapshot.snapshot_id not in snapshot_ids:
            snapshot_ids.append(snapshot.snapshot_id)
    return snapshot_ids


def _owner_brief_suggested_action_keys(cases: list[OperationalCase]) -> list[str]:
    keys: list[str] = []
    for case in cases:
        for action_key in _case_suggested_action_keys(case):
            if action_key not in keys:
                keys.append(action_key)
    return keys


def _owner_brief_action_catalog(action_keys: list[str]) -> list[dict[str, Any]]:
    return [
        ACTION_CATALOG[action_key].operator_projection(can_execute_case_actions=False)
        for action_key in action_keys
        if action_key in ACTION_CATALOG
    ]


def preview_owner_case_brief(
    store: OperationalCaseStore,
    *,
    business_id: str,
    business_name: str | None = None,
    report_date: str | None = None,
    max_cases: str | None = None,
) -> dict[str, Any]:
    """Read-only owner WhatsApp brief projection from canonical Operational Cases.

    This helper intentionally returns projection metadata plus composed text only;
    it does not dispatch, mutate case state, or treat WhatsApp copy as source of
    truth. Case selection comes from the canonical case store and is tenant
    scoped before text composition.
    """

    parsed_max_cases = parse_limit(max_cases, default=3, max_limit=10, parameter_name="max_cases")
    parsed_report_date = _parse_report_date(report_date)
    safe_business_name = redact_text((business_name or business_id).strip() or business_id) or "[REDACTED]"
    actionable = _owner_brief_cases(store, business_id)
    visible = actionable[:parsed_max_cases]
    displayed_action_keys = _owner_brief_suggested_action_keys(visible)
    text = compose_owner_case_brief(
        safe_business_name,
        actionable,
        report_date=parsed_report_date,
        max_cases=parsed_max_cases,
    )
    payload = {
        "business_id": business_id,
        "business_name": safe_business_name,
        "projection_type": "owner_case_brief",
        "channel": "whatsapp",
        "report_date": parsed_report_date.isoformat() if parsed_report_date is not None else None,
        "max_cases": parsed_max_cases,
        "total_actionable_cases": len(actionable),
        "displayed_case_count": len(visible),
        "truncated": len(actionable) > len(visible),
        "case_ids": [case.case_id for case in visible],
        "displayed_cases": _owner_brief_displayed_cases(visible),
        "suggested_action_keys": displayed_action_keys,
        "action_catalog": _owner_brief_action_catalog(displayed_action_keys),
        "evidence_freshness": _owner_brief_evidence_freshness(visible=visible, actionable=actionable),
        "text": text,
    }
    return redact_secrets(payload)


__all__ = [name for name in globals() if not name.startswith("__")]

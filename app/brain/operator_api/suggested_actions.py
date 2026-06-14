from __future__ import annotations

from app.brain.action_catalog import is_supported_suggested_action_key

from .common import *  # noqa: F401,F403
from .projections import _case_suggested_action_keys, _case_suggested_actions


def _parse_suggested_action_key_filter(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate not in ACTION_CATALOG:
        raise OperatorAPIError(
            "unknown_suggested_action_key",
            f"unknown suggested action_key: {candidate}",
            status_code=400,
        )
    if not is_supported_suggested_action_key(candidate):
        raise OperatorAPIError(
            "unsupported_suggested_action_key",
            f"unsupported suggested action_key for case projections: {candidate}",
            status_code=400,
        )
    return candidate


def list_suggested_action_cases(
    store: OperationalCaseStore,
    *,
    business_id: str,
    limit: str | None = None,
    action_key: str | None = None,
) -> dict[str, Any]:
    """Top actionable cases that have registered suggested action keys.

    Suggested actions are read-only operator projections over canonical case
    metadata populated by deterministic detections. This helper deliberately
    ignores invented/unregistered keys, excludes terminal cases, and orders the
    queue by priority before recency so operators see the most urgent suggested
    next steps first without making this surface a workflow source of truth.
    """

    parsed_limit = parse_limit(limit)
    parsed_action_key = _parse_suggested_action_key_filter(action_key)
    suggested: list[tuple[int, datetime, str, OperationalCase, list[str], list[dict[str, Any]]]] = []
    for status in ("open", "acknowledged", "in_progress"):
        for case in store.list_cases(business_id=business_id, status=status, limit=None):
            action_keys = _case_suggested_action_keys(case)
            if not action_keys:
                continue
            if parsed_action_key is not None:
                if parsed_action_key not in action_keys:
                    continue
                action_keys = [parsed_action_key]
            actions = _case_suggested_actions(case)
            if parsed_action_key is not None:
                actions = [action for action in actions if action.get("action_key") == parsed_action_key]
            suggested.append(
                (
                    case.priority_score,
                    case.opened_at.astimezone(timezone.utc),
                    case.case_id,
                    case,
                    action_keys,
                    actions,
                )
            )

    suggested.sort(key=lambda item: (-item[0], -item[1].timestamp(), item[2]))
    limited = suggested[:parsed_limit]
    cases_payload = [
        {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "title": case.title,
            "status": case.status,
            "severity": case.severity,
            "priority_score": case.priority_score,
            "entity_scope": case.entity_scope,
            "opened_at": case.opened_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
            "latest_run_id": case.latest_run_id,
            "suggested_action_keys": action_keys,
            "suggested_actions": actions,
            "action_count": len(action_keys),
        }
        for _priority, _opened_at, _case_id, case, action_keys, actions in limited
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "filters": {"action_key": parsed_action_key},
            "suggested_total": len(suggested),
            "cases": cases_payload,
            "limit": parsed_limit,
            "count": len(cases_payload),
        }
    )


__all__ = [name for name in globals() if not name.startswith("__")]

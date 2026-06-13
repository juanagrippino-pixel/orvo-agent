from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, TypeAlias

from .common import *  # noqa: F401,F403
from .commented_cases import list_recently_commented_cases
from .recent_cases import (
    list_recently_acknowledged_cases,
    list_recently_assigned_cases,
    list_recently_dismissed_cases,
    list_recently_in_progress_cases,
    list_recently_opened_cases,
    list_recently_reopened_cases,
    list_recently_resolved_cases,
)
from .updated_cases import list_recently_updated_cases

RecentCaseActivityType: TypeAlias = Literal[
    "opened",
    "acknowledged",
    "in_progress",
    "assigned",
    "commented",
    "updated",
    "reopened",
    "resolved",
    "dismissed",
]

_RecentProjection = Callable[..., dict[str, Any]]
_RECENT_ACTIVITY_DEFAULT: RecentCaseActivityType = "updated"
_RECENT_ACTIVITY_PROJECTIONS: dict[RecentCaseActivityType, tuple[_RecentProjection, str]] = {
    "opened": (list_recently_opened_cases, "open_total"),
    "acknowledged": (list_recently_acknowledged_cases, "acknowledged_total"),
    "in_progress": (list_recently_in_progress_cases, "in_progress_total"),
    "assigned": (list_recently_assigned_cases, "assigned_total"),
    "commented": (list_recently_commented_cases, "commented_total"),
    "updated": (list_recently_updated_cases, "updated_total"),
    "reopened": (list_recently_reopened_cases, "reopened_total"),
    "resolved": (list_recently_resolved_cases, "resolved_total"),
    "dismissed": (list_recently_dismissed_cases, "dismissed_total"),
}


def parse_recent_case_activity_type(value: str | None) -> RecentCaseActivityType:
    if value in (None, ""):
        return _RECENT_ACTIVITY_DEFAULT
    normalized = value.strip().lower().replace("-", "_")
    if normalized not in _RECENT_ACTIVITY_PROJECTIONS:
        raise OperatorAPIError(
            "invalid_recent_activity_type",
            f"unsupported recent activity type: {value}",
            status_code=400,
        )
    return normalized  # type: ignore[return-value]


def list_recent_case_activity(
    store: OperationalCaseStore,
    *,
    business_id: str,
    activity_type: str | None = None,
    limit: str | None = None,
) -> dict[str, Any]:
    """Return a shared recent-activity surface over canonical case projections.

    This wrapper keeps legacy/specialized recently-* projections intact while
    giving operator surfaces a single route/query model for recent activity.
    The underlying case rows remain projection-specific, but the top-level
    envelope is normalized so thin adapters do not need one endpoint per recent
    workflow slice.
    """

    parsed_activity_type = parse_recent_case_activity_type(activity_type)
    projection, total_key = _RECENT_ACTIVITY_PROJECTIONS[parsed_activity_type]
    result = projection(store, business_id=business_id, limit=limit)
    total = int(result.get(total_key, result.get("count", 0)))
    return redact_secrets(
        {
            "business_id": business_id,
            "projection_type": "recent_case_activity",
            "activity_type": parsed_activity_type,
            "total": total,
            "limit": result.get("limit"),
            "count": result.get("count", 0),
            "cases": result.get("cases", []),
        }
    )


__all__ = [name for name in globals() if not name.startswith("__")]

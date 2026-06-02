from __future__ import annotations

from typing import Any, Literal, get_args
from datetime import datetime, timezone

from app.brain.action_catalog import API_ENABLED_CASE_ACTION_KEYS, list_case_action_catalog
from app.brain.operational_cases import (
    ACTIONABLE_OPERATIONAL_CASE_STATUSES,
    TERMINAL_OPERATIONAL_CASE_STATUSES,
    ActorType,
    OperationalCase,
    OperationalCaseStatus,
    OperationalCaseStatusError,
    OperationalCaseStore,
    TimelineEventType,
)
from app.brain.operator_case_projections import (
    is_case_degraded as _is_degraded,
    latest_evidence_at as _latest_evidence_at,
    source_connectors as _source_connectors,
)
from app.brain.run_ledger import RunLedger, RunRecord, RunStatus
from app.brain.security.redaction import redact_secrets, redact_text

CaseActionKey = Literal[
    "acknowledge_case",
    "assign_owner",
    "mark_in_progress",
    "resolve_case",
    "dismiss_case",
    "add_comment",
]
_ALLOWED_CASE_ACTIONS: set[str] = set(API_ENABLED_CASE_ACTION_KEYS)
_ALLOWED_CASE_STATUSES: set[str] = set(get_args(OperationalCaseStatus))
_ALLOWED_RUN_STATUSES: set[str] = set(get_args(RunStatus))
_ALLOWED_TIMELINE_EVENT_TYPES: set[str] = set(get_args(TimelineEventType))
_ALLOWED_TIMELINE_ACTOR_TYPES: set[str] = set(get_args(ActorType))
_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


class OperatorAPIError(Exception):
    """Safe error intended for API envelopes."""

    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        self.code = code
        self.message = redact_text(message) or "Operator API error"
        self.status_code = status_code
        super().__init__(self.message)

def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def parse_limit(value: str | None, *, default: int = _DEFAULT_LIMIT, max_limit: int = _MAX_LIMIT) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise OperatorAPIError("invalid_limit", "limit must be an integer", status_code=400) from exc
    if parsed < 1:
        raise OperatorAPIError("invalid_limit", "limit must be positive", status_code=400)
    return min(parsed, max_limit)

def parse_case_status(value: str | None) -> OperationalCaseStatus | None:
    if value in (None, ""):
        return None
    if value not in _ALLOWED_CASE_STATUSES:
        raise OperatorAPIError("invalid_case_status", f"unsupported case status: {value}", status_code=400)
    return value  # type: ignore[return-value]

def parse_timeline_event_type(value: str | None) -> TimelineEventType | None:
    if value in (None, ""):
        return None
    if value not in _ALLOWED_TIMELINE_EVENT_TYPES:
        raise OperatorAPIError(
            "invalid_timeline_event_type",
            f"unsupported timeline event_type: {value}",
            status_code=400,
        )
    return value  # type: ignore[return-value]

def parse_timeline_actor_type(value: str | None) -> ActorType | None:
    if value in (None, ""):
        return None
    if value not in _ALLOWED_TIMELINE_ACTOR_TYPES:
        raise OperatorAPIError(
            "invalid_timeline_actor_type",
            f"unsupported timeline actor_type: {value}",
            status_code=400,
        )
    return value  # type: ignore[return-value]

def parse_run_status(value: str | None) -> RunStatus | None:
    if value in (None, ""):
        return None
    if value not in _ALLOWED_RUN_STATUSES:
        raise OperatorAPIError("invalid_run_status", f"unsupported run status: {value}", status_code=400)
    return value  # type: ignore[return-value]

def normalize_operator_actor(actor_ref: Any, actor: Any) -> str:
    effective_actor_ref = actor_ref if actor_ref is not None else actor
    if effective_actor_ref is None:
        raise OperatorAPIError("missing_operator_actor", "operator actor is required", status_code=400)
    if not isinstance(effective_actor_ref, str):
        raise OperatorAPIError("invalid_operator_actor", "operator actor must be a string", status_code=400)
    normalized = effective_actor_ref.strip()
    if not normalized:
        raise OperatorAPIError("missing_operator_actor", "operator actor is required", status_code=400)
    return normalized

def normalize_case_assignee(assignee_ref: Any, owner_ref: Any) -> str:
    effective_assignee_ref = assignee_ref if assignee_ref is not None else owner_ref
    if effective_assignee_ref is None:
        raise OperatorAPIError("invalid_assignee_ref", "assignee_ref must be a non-empty string", status_code=400)
    if not isinstance(effective_assignee_ref, str):
        raise OperatorAPIError("invalid_assignee_ref", "assignee_ref must be a non-empty string", status_code=400)
    normalized = effective_assignee_ref.strip()
    if not normalized:
        raise OperatorAPIError("invalid_assignee_ref", "assignee_ref must be a non-empty string", status_code=400)
    return normalized

_ACTIONABLE_STATUSES = ACTIONABLE_OPERATIONAL_CASE_STATUSES


_AGE_BUCKETS: tuple[tuple[str, int | None], ...] = (
    ("under_1h", 3600),
    ("under_6h", 21600),
    ("under_24h", 86400),
    ("under_7d", 604800),
    ("over_7d", None),
)


def _now_utc() -> datetime:
    # Backward compatibility: legacy tests and callers patch
    # ``app.brain.operator_api._now_utc`` at package level. Split modules keep
    # importing this common helper, so honor a package-level replacement when
    # present instead of bypassing it.
    import sys

    package = sys.modules.get("app.brain.operator_api")
    override = getattr(package, "_now_utc", None) if package is not None else None
    if override is not None and override is not _now_utc:
        return override()
    return datetime.now(timezone.utc)

def _classify_age_bucket(age_seconds: int) -> str:
    for name, upper in _AGE_BUCKETS:
        if upper is None or age_seconds < upper:
            return name
    return _AGE_BUCKETS[-1][0]

def _classify_priority_bracket(priority_score: int) -> str:
    if priority_score < 50:
        return "low"
    if priority_score < 80:
        return "medium"
    return "high"

_FRESHNESS_RANK: dict[str, int] = {
    "fresh": 0,
    "degraded": 1,
    "stale": 2,
    "missing": 3,
}


def _worst_freshness_state(case: OperationalCase) -> str | None:
    worst: str | None = None
    worst_rank = -1
    for snapshot in case.evidence_snapshots:
        rank = _FRESHNESS_RANK.get(snapshot.freshness_state, -1)
        if rank > worst_rank:
            worst_rank = rank
            worst = snapshot.freshness_state
    return worst

def _latency_summary(seconds: list[int]) -> dict[str, int]:
    if not seconds:
        return {}
    sorted_seconds = sorted(seconds)
    count = len(sorted_seconds)
    midpoint = count // 2
    if count % 2 == 1:
        median = sorted_seconds[midpoint]
    else:
        median = (sorted_seconds[midpoint - 1] + sorted_seconds[midpoint]) // 2
    return {
        "min": sorted_seconds[0],
        "max": sorted_seconds[-1],
        "avg": sum(sorted_seconds) // count,
        "median": median,
    }

__all__ = [name for name in globals() if not name.startswith("__")]

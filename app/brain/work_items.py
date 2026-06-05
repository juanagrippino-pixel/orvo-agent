"""WorkItem projection helpers for Jira-like operator surfaces.

OperationalCase remains the durable source of truth. This module exposes a
small additive projection/registry layer so API, JQL-lite, and future boards can
share project, issue-type, workflow, and status-category semantics without
creating a parallel task store.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, get_args

from app.brain.operational_cases import (
    ACTIONABLE_OPERATIONAL_CASE_STATUSES,
    DETECTABLE_OPERATIONAL_CASE_TYPES,
    OWNER_FACING_OPERATIONAL_CASE_TYPES,
    TERMINAL_OPERATIONAL_CASE_STATUSES,
    OperationalCase,
    OperationalCaseStatus,
    OperationalCaseStatusCategory,
    OperationalCaseType,
    operational_case_status_category,
    operational_case_status_transitions,
    operational_case_system_reopen_transitions,
)
from app.brain.semantics import CASE_FAMILY_METRICS

_PROJECT_KEY_MAX_LENGTH = 32
_DEFAULT_CASE_TYPE_SCHEME_ID = "d2c-default-case-types"
_DEFAULT_WORKFLOW_SCHEME_ID = "operational-case-default-workflow"
_DEFAULT_WORKFLOW_ID = "operational-case-default"


def _iso_utc(value: Any) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("work item SLA timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def project_key_for_business(business_id: str) -> str:
    """Derive a stable internal project key from the route-owned business scope."""

    normalized = re.sub(r"[^A-Za-z0-9]+", "_", business_id.strip()).strip("_").upper()
    if not normalized:
        normalized = "PROJECT"
    if normalized[0].isdigit():
        normalized = f"B_{normalized}"
    if len(normalized) <= _PROJECT_KEY_MAX_LENGTH:
        return normalized

    suffix = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:8].upper()
    prefix_length = _PROJECT_KEY_MAX_LENGTH - len(suffix)
    return f"{normalized[:prefix_length]}{suffix}"


def project_projection(business_id: str) -> dict[str, str]:
    """Return the default project/workspace projection for a business."""

    return {
        "project_id": f"business:{business_id}",
        "business_id": business_id,
        "project_key": project_key_for_business(business_id),
        "display_name": business_id,
        "case_type_scheme_id": _DEFAULT_CASE_TYPE_SCHEME_ID,
        "workflow_scheme_id": _DEFAULT_WORKFLOW_SCHEME_ID,
    }


def case_project_key(case: OperationalCase) -> str:
    return project_key_for_business(case.business_id)


def case_issue_type(case: OperationalCase) -> OperationalCaseType:
    return case.case_type


def case_status_category(case: OperationalCase) -> OperationalCaseStatusCategory:
    return operational_case_status_category(case.status)


def priority_bracket_for_score(priority_score: int) -> str:
    """Return the canonical WorkItem priority bracket for a deterministic score."""

    if priority_score < 50:
        return "low"
    if priority_score < 80:
        return "medium"
    return "high"


def case_priority_bracket(case: OperationalCase) -> str:
    return priority_bracket_for_score(case.priority_score)


def case_work_item_id(case: OperationalCase) -> str:
    return f"{case_project_key(case)}:{case.case_id}"


def _case_comment_events(case: OperationalCase) -> list[Any]:
    """Return timeline-backed comments without copying bodies into queue projections."""

    return [event for event in case.timeline if event.event_type == "operator_comment"]


def case_comment_count(case: OperationalCase) -> int:
    return len(_case_comment_events(case))


def case_last_commented_at(case: OperationalCase) -> str | None:
    comment_events = _case_comment_events(case)
    if not comment_events:
        return None
    return _iso_utc(max(event.created_at for event in comment_events))


def acknowledgment_sla_minutes_for_priority_score(priority_score: int) -> int:
    """Return the deterministic first-acknowledgment SLA target for a priority score."""

    bracket = priority_bracket_for_score(priority_score)
    if bracket == "high":
        return 60
    if bracket == "medium":
        return 180
    return 1440


def resolution_sla_minutes_for_priority_score(priority_score: int) -> int:
    """Return the deterministic time-to-resolution SLA target for a priority score."""

    bracket = priority_bracket_for_score(priority_score)
    if bracket == "high":
        return 1440
    if bracket == "medium":
        return 4320
    return 10080


def case_acknowledgment_due_at(case: OperationalCase) -> datetime:
    return case.opened_at + timedelta(minutes=acknowledgment_sla_minutes_for_priority_score(case.priority_score))


def case_resolution_due_at(case: OperationalCase) -> datetime:
    return case.opened_at + timedelta(minutes=resolution_sla_minutes_for_priority_score(case.priority_score))


def _acknowledgment_sla_comparison_time(case: OperationalCase, *, as_of: datetime) -> datetime:
    """Return the timestamp that stops the first-ack SLA clock.

    The canonical acknowledgment timestamp wins when present. For cases closed
    directly from ``open`` (for example duplicate/false-positive dismissals), the
    terminal timestamp stops the clock so old done cases do not become newly
    overdue just because an operator dashboard is viewed later.
    """

    if case.acknowledged_at is not None:
        return case.acknowledged_at
    if case.resolved_at is not None:
        return case.resolved_at
    if case.dismissed_at is not None:
        return case.dismissed_at
    return _as_utc(as_of)


def _resolution_sla_comparison_time(case: OperationalCase, *, as_of: datetime) -> datetime:
    """Return the timestamp that stops the time-to-resolution SLA clock."""

    if case.resolved_at is not None:
        return case.resolved_at
    if case.dismissed_at is not None:
        return case.dismissed_at
    return _as_utc(as_of)


def case_acknowledgment_sla_breached(case: OperationalCase, *, as_of: datetime) -> bool:
    due_at = case_acknowledgment_due_at(case)
    comparison_time = _acknowledgment_sla_comparison_time(case, as_of=as_of)
    return comparison_time > due_at


def case_resolution_sla_breached(case: OperationalCase, *, as_of: datetime) -> bool:
    due_at = case_resolution_due_at(case)
    comparison_time = _resolution_sla_comparison_time(case, as_of=as_of)
    return comparison_time > due_at


def case_work_item_projection(case: OperationalCase, *, as_of: datetime | None = None) -> dict[str, Any]:
    """Project an OperationalCase as a WorkItem-shaped API object."""

    effective_as_of = _as_utc(as_of) if as_of is not None else datetime.now(tz=timezone.utc)

    return {
        "work_item_id": case_work_item_id(case),
        "project_key": case_project_key(case),
        "issue_type": case_issue_type(case),
        "status": case.status,
        "status_category": case_status_category(case),
        "priority_score": case.priority_score,
        "priority_bracket": case_priority_bracket(case),
        "assignee_ref": case.assignee_ref,
        "assigned_at": _iso_utc(case.assigned_at) if case.assigned_at is not None else None,
        "comment_count": case_comment_count(case),
        "last_commented_at": case_last_commented_at(case),
        "acknowledged_at": _iso_utc(case.acknowledged_at) if case.acknowledged_at is not None else None,
        "acknowledgment_sla_minutes": acknowledgment_sla_minutes_for_priority_score(case.priority_score),
        "acknowledgment_due_at": _iso_utc(case_acknowledgment_due_at(case)),
        "acknowledgment_sla_breached": case_acknowledgment_sla_breached(case, as_of=effective_as_of),
        "resolved_at": _iso_utc(case.resolved_at) if case.resolved_at is not None else None,
        "resolution_sla_minutes": resolution_sla_minutes_for_priority_score(case.priority_score),
        "resolution_due_at": _iso_utc(case_resolution_due_at(case)),
        "resolution_sla_breached": case_resolution_sla_breached(case, as_of=effective_as_of),
        "created_at": _iso_utc(case.opened_at),
        "updated_at": _iso_utc(case.updated_at),
        "case_id": case.case_id,
    }


def operational_case_issue_type_definitions() -> list[dict[str, Any]]:
    """Expose current D2C case families as issue-type definitions."""

    definitions: list[dict[str, Any]] = []
    for case_type in get_args(OperationalCaseType):
        detectable = case_type in DETECTABLE_OPERATIONAL_CASE_TYPES
        owner_facing = case_type in OWNER_FACING_OPERATIONAL_CASE_TYPES
        definitions.append(
            {
                "issue_type": case_type,
                "case_type": case_type,
                "scheme_id": _DEFAULT_CASE_TYPE_SCHEME_ID,
                "detectable": detectable,
                "owner_facing": owner_facing,
                "visibility": "owner_facing" if owner_facing else "internal_deferred",
                "required_metric_keys": list(CASE_FAMILY_METRICS.get(case_type, ())),
            }
        )
    return definitions


def operational_case_status_definitions() -> list[dict[str, Any]]:
    """Expose current status metadata without enabling custom workflows."""

    transitions = operational_case_status_transitions()
    system_reopen_transitions = operational_case_system_reopen_transitions()
    return [
        {
            "status": status,
            "status_category": operational_case_status_category(status),
            "actionable": status in ACTIONABLE_OPERATIONAL_CASE_STATUSES,
            "terminal": status in TERMINAL_OPERATIONAL_CASE_STATUSES,
            "transitions": sorted(transitions[status]),
            "system_reopen_transition": system_reopen_transitions.get(status),
        }
        for status in get_args(OperationalCaseStatus)
    ]


def operational_case_workflow_definition() -> dict[str, Any]:
    """Expose the current deterministic OperationalCase workflow definition."""

    transitions = operational_case_status_transitions()
    operator_transitions = {status: sorted(targets) for status, targets in transitions.items()}
    system_reopen_transitions = operational_case_system_reopen_transitions()
    system_recurrence_transitions = {
        status: [target_status]
        for status, target_status in system_reopen_transitions.items()
    }
    return {
        "workflow_id": _DEFAULT_WORKFLOW_ID,
        "workflow_scheme_id": _DEFAULT_WORKFLOW_SCHEME_ID,
        "statuses": operational_case_status_definitions(),
        "transitions": operator_transitions,
        "system_reopen_transitions": system_reopen_transitions,
        "transition_actor_boundaries": {
            "operator": operator_transitions,
            "system_recurrence": system_recurrence_transitions,
        },
        "tenant_customizable": False,
    }


def allowed_status_categories() -> set[str]:
    return set(get_args(OperationalCaseStatusCategory))

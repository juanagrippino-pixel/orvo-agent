"""WorkItem projection helpers for Jira-like operator surfaces.

OperationalCase remains the durable source of truth. This module exposes a
small additive projection/registry layer so API, JQL-lite, and future boards can
share project, issue-type, workflow, and status-category semantics without
creating a parallel task store.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import timezone
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


@dataclass(frozen=True)
class WorkItemPriorityDefinition:
    bracket: str
    label: str
    lower_bound: int
    upper_bound: int


_PRIORITY_DEFINITIONS: tuple[WorkItemPriorityDefinition, ...] = (
    WorkItemPriorityDefinition("low", "Low", 0, 49),
    WorkItemPriorityDefinition("medium", "Medium", 50, 79),
    WorkItemPriorityDefinition("high", "High", 80, 100),
)


def _iso_utc(value: Any) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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
    """Return the canonical WorkItem priority bracket for a 0..100 score."""

    for definition in _PRIORITY_DEFINITIONS:
        if definition.lower_bound <= priority_score <= definition.upper_bound:
            return definition.bracket
    if priority_score < _PRIORITY_DEFINITIONS[0].lower_bound:
        return _PRIORITY_DEFINITIONS[0].bracket
    return _PRIORITY_DEFINITIONS[-1].bracket


def case_priority_bracket(case: OperationalCase) -> str:
    return priority_bracket_for_score(case.priority_score)


def allowed_priority_brackets() -> set[str]:
    return {definition.bracket for definition in _PRIORITY_DEFINITIONS}


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


def case_work_item_projection(case: OperationalCase) -> dict[str, Any]:
    """Project an OperationalCase as a WorkItem-shaped API object."""

    return {
        "work_item_id": case_work_item_id(case),
        "project_key": case_project_key(case),
        "issue_type": case_issue_type(case),
        "status": case.status,
        "status_category": case_status_category(case),
        "priority_score": case.priority_score,
        "priority_bracket": case_priority_bracket(case),
        "assignee_ref": case.assignee_ref,
        "comment_count": case_comment_count(case),
        "last_commented_at": case_last_commented_at(case),
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


def operational_case_priority_definitions() -> list[dict[str, Any]]:
    """Expose the canonical priority-bracket scheme for WorkItem projections."""

    return [
        {
            "bracket": definition.bracket,
            "label": definition.label,
            "lower_bound": definition.lower_bound,
            "upper_bound": definition.upper_bound,
        }
        for definition in _PRIORITY_DEFINITIONS
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

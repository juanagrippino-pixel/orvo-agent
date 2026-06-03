"""WorkItem projection helpers for Jira-like operator surfaces.

OperationalCase remains the durable source of truth. This module exposes a
small additive projection/registry layer so API, JQL-lite, and future boards can
share project, issue-type, workflow, and status-category semantics without
creating a parallel task store.
"""

from __future__ import annotations

import hashlib
import re
from datetime import timezone
from typing import Any, get_args

from app.brain.operational_cases import (
    ACTIONABLE_OPERATIONAL_CASE_STATUSES,
    TERMINAL_OPERATIONAL_CASE_STATUSES,
    OperationalCase,
    OperationalCaseStatus,
    OperationalCaseStatusCategory,
    OperationalCaseType,
    operational_case_status_category,
    operational_case_status_transitions,
)

_PROJECT_KEY_MAX_LENGTH = 32
_DEFAULT_CASE_TYPE_SCHEME_ID = "d2c-default-case-types"
_DEFAULT_WORKFLOW_SCHEME_ID = "operational-case-default-workflow"
_DEFAULT_WORKFLOW_ID = "operational-case-default"


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


def case_work_item_id(case: OperationalCase) -> str:
    return f"{case_project_key(case)}:{case.case_id}"


def case_work_item_projection(case: OperationalCase) -> dict[str, Any]:
    """Project an OperationalCase as a WorkItem-shaped API object."""

    return {
        "work_item_id": case_work_item_id(case),
        "project_key": case_project_key(case),
        "issue_type": case_issue_type(case),
        "status": case.status,
        "status_category": case_status_category(case),
        "priority_score": case.priority_score,
        "assignee_ref": case.assignee_ref,
        "created_at": _iso_utc(case.opened_at),
        "updated_at": _iso_utc(case.updated_at),
        "case_id": case.case_id,
    }


def operational_case_issue_type_definitions() -> list[dict[str, str]]:
    """Expose current D2C case families as issue-type definitions."""

    return [
        {
            "issue_type": case_type,
            "case_type": case_type,
            "scheme_id": _DEFAULT_CASE_TYPE_SCHEME_ID,
        }
        for case_type in get_args(OperationalCaseType)
    ]


def operational_case_status_definitions() -> list[dict[str, Any]]:
    """Expose current status metadata without enabling custom workflows."""

    transitions = operational_case_status_transitions()
    return [
        {
            "status": status,
            "status_category": operational_case_status_category(status),
            "actionable": status in ACTIONABLE_OPERATIONAL_CASE_STATUSES,
            "terminal": status in TERMINAL_OPERATIONAL_CASE_STATUSES,
            "transitions": sorted(transitions[status]),
        }
        for status in get_args(OperationalCaseStatus)
    ]


def operational_case_workflow_definition() -> dict[str, Any]:
    """Expose the current deterministic OperationalCase workflow definition."""

    transitions = operational_case_status_transitions()
    return {
        "workflow_id": _DEFAULT_WORKFLOW_ID,
        "workflow_scheme_id": _DEFAULT_WORKFLOW_SCHEME_ID,
        "statuses": operational_case_status_definitions(),
        "transitions": {status: sorted(targets) for status, targets in transitions.items()},
        "tenant_customizable": False,
    }


def allowed_status_categories() -> set[str]:
    return set(get_args(OperationalCaseStatusCategory))

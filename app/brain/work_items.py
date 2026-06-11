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
from typing import Any, Literal, get_args

from app.brain.operational_cases import (
    ACTIONABLE_OPERATIONAL_CASE_STATUSES,
    TERMINAL_OPERATIONAL_CASE_STATUSES,
    OperationalCase,
    OperationalCaseSeverity,
    OperationalCaseStatus,
    OperationalCaseStatusCategory,
    OperationalCaseType,
    operational_case_status_category,
    operational_case_system_status_transitions,
    operational_case_status_transitions,
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


WorkItemQueryFieldValueType = Literal["bool", "enum", "int", "string", "datetime"]
OperationalCaseIssueTypeReleaseState = Literal["promoted", "deferred", "internal_only"]


@dataclass(frozen=True)
class WorkItemQueryFieldDefinition:
    """Canonical allowlisted field definition for WorkItem/Case projections.

    The registry describes query/view/facet semantics over OperationalCase and
    WorkItem projections. It intentionally does not define business metrics or
    aliases; those remain owned by the semantic MetricRegistry.
    """

    field: str
    value_type: WorkItemQueryFieldValueType
    allowed_values: frozenset[str] | None = None
    allowed_operators: frozenset[str] = frozenset({"=", "!=", "IN"})
    sortable: bool = False
    facetable: bool = False


_PRIORITY_DEFINITIONS: tuple[WorkItemPriorityDefinition, ...] = (
    WorkItemPriorityDefinition("low", "Low", 0, 49),
    WorkItemPriorityDefinition("medium", "Medium", 50, 79),
    WorkItemPriorityDefinition("high", "High", 80, 100),
)

_RANGE_OPERATORS = frozenset({"=", "!=", ">", ">=", "<", "<="})

_WORK_ITEM_QUERY_FIELD_DEFINITIONS: tuple[WorkItemQueryFieldDefinition, ...] = (
    WorkItemQueryFieldDefinition("status", "enum", frozenset(get_args(OperationalCaseStatus)), facetable=True),
    WorkItemQueryFieldDefinition(
        "status_category",
        "enum",
        frozenset(get_args(OperationalCaseStatusCategory)),
        facetable=True,
    ),
    WorkItemQueryFieldDefinition("project", "string", facetable=True),
    WorkItemQueryFieldDefinition("issue_type", "enum", frozenset(get_args(OperationalCaseType)), facetable=True),
    WorkItemQueryFieldDefinition(
        "release_state",
        "enum",
        frozenset(get_args(OperationalCaseIssueTypeReleaseState)),
        facetable=True,
    ),
    WorkItemQueryFieldDefinition("assignee_ref", "string", facetable=True),
    WorkItemQueryFieldDefinition("case_type", "enum", frozenset(get_args(OperationalCaseType)), facetable=True),
    WorkItemQueryFieldDefinition("severity", "enum", frozenset(get_args(OperationalCaseSeverity)), facetable=True),
    WorkItemQueryFieldDefinition("priority_score", "int", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition(
        "priority_bracket",
        "enum",
        frozenset({definition.bracket for definition in _PRIORITY_DEFINITIONS}),
        facetable=True,
    ),
    WorkItemQueryFieldDefinition("entity.kind", "string", facetable=True),
    WorkItemQueryFieldDefinition("entity.id", "string"),
    WorkItemQueryFieldDefinition("entity.label", "string", allowed_operators=frozenset({"=", "!="})),
    WorkItemQueryFieldDefinition("latest_run_id", "string"),
    WorkItemQueryFieldDefinition("source_connector", "string", facetable=True),
    WorkItemQueryFieldDefinition("degraded", "bool", allowed_operators=frozenset({"=", "!="}), facetable=True),
    WorkItemQueryFieldDefinition("dedupe_key", "string", allowed_operators=frozenset({"=", "!="})),
    WorkItemQueryFieldDefinition("opened_at", "datetime", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition("updated_at", "datetime", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition("resolved_at", "datetime", allowed_operators=_RANGE_OPERATORS),
)

_WORK_ITEM_QUERY_FIELD_BY_KEY = {definition.field: definition for definition in _WORK_ITEM_QUERY_FIELD_DEFINITIONS}


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


def case_type_release_state(case_type: str) -> OperationalCaseIssueTypeReleaseState:
    """Return the release state for an OperationalCase issue type.

    The semantic registry remains the promotion gate. Case families with
    ``CASE_FAMILY_METRICS`` evidence contracts are promoted; implemented future
    catalog targets without evidence contracts stay deferred so operator/API
    projections cannot accidentally present them as owner-facing/detectable.
    """

    if case_type in CASE_FAMILY_METRICS:
        return "promoted"
    if case_type in get_args(OperationalCaseType):
        return "deferred"
    return "internal_only"


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


def work_item_query_field_spec(field: str) -> WorkItemQueryFieldDefinition | None:
    """Return the canonical query field definition, if the field is allowlisted."""

    return _WORK_ITEM_QUERY_FIELD_BY_KEY.get(field)


def allowed_work_item_query_sort_fields() -> set[str]:
    """Return canonical fields allowed in JQL-lite ORDER BY clauses."""

    return {definition.field for definition in _WORK_ITEM_QUERY_FIELD_DEFINITIONS if definition.sortable}


def allowed_work_item_facet_fields() -> set[str]:
    """Return canonical WorkItem fields allowed for faceted operator counts."""

    return {definition.field for definition in _WORK_ITEM_QUERY_FIELD_DEFINITIONS if definition.facetable}


def work_item_query_field_definitions() -> list[dict[str, Any]]:
    """Expose canonical query-field metadata for tests/docs/operator surfaces."""

    return [
        {
            "field": definition.field,
            "value_type": definition.value_type,
            "allowed_values": sorted(definition.allowed_values) if definition.allowed_values is not None else None,
            "allowed_operators": sorted(definition.allowed_operators),
            "sortable": definition.sortable,
            "facetable": definition.facetable,
        }
        for definition in _WORK_ITEM_QUERY_FIELD_DEFINITIONS
    ]


def case_work_item_id(case: OperationalCase) -> str:
    return f"{case_project_key(case)}:{case.case_id}"


def case_work_item_projection(case: OperationalCase) -> dict[str, Any]:
    """Project an OperationalCase as a WorkItem-shaped API object."""

    return {
        "work_item_id": case_work_item_id(case),
        "project_key": case_project_key(case),
        "issue_type": case_issue_type(case),
        "release_state": case_type_release_state(case.case_type),
        "status": case.status,
        "status_category": case_status_category(case),
        "priority_score": case.priority_score,
        "priority_bracket": case_priority_bracket(case),
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
            "release_state": case_type_release_state(case_type),
        }
        for case_type in get_args(OperationalCaseType)
    ]


def operational_case_status_definitions() -> list[dict[str, Any]]:
    """Expose current status metadata without enabling custom workflows."""

    transitions = operational_case_status_transitions()
    system_transitions = operational_case_system_status_transitions()
    return [
        {
            "status": status,
            "status_category": operational_case_status_category(status),
            "actionable": status in ACTIONABLE_OPERATIONAL_CASE_STATUSES,
            "terminal": status in TERMINAL_OPERATIONAL_CASE_STATUSES,
            "transitions": sorted(transitions[status]),
            "system_transitions": sorted(system_transitions[status]),
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
    system_transitions = operational_case_system_status_transitions()
    return {
        "workflow_id": _DEFAULT_WORKFLOW_ID,
        "workflow_scheme_id": _DEFAULT_WORKFLOW_SCHEME_ID,
        "statuses": operational_case_status_definitions(),
        "transitions": {status: sorted(targets) for status, targets in transitions.items()},
        "manual_transitions": {status: sorted(targets) for status, targets in transitions.items()},
        "system_transitions": {status: sorted(targets) for status, targets in system_transitions.items()},
        "system_transition_events": [
            {
                "event_type": "case_reopened",
                "actor_type": "system",
                "from_status": status,
                "to_status": target,
            }
            for status in sorted(system_transitions)
            for target in sorted(system_transitions[status])
        ],
        "tenant_customizable": False,
    }


def allowed_status_categories() -> set[str]:
    return set(get_args(OperationalCaseStatusCategory))

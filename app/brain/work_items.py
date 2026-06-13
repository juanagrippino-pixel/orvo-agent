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
from datetime import datetime, timezone
from typing import Any, Literal, get_args

from app.brain.operational_cases import (
    ACTIONABLE_OPERATIONAL_CASE_STATUSES,
    OWNER_FACING_OPERATIONAL_CASE_TYPES,
    READINESS_GATED_OPERATIONAL_CASE_TYPES,
    TERMINAL_OPERATIONAL_CASE_STATUSES,
    OperationalCase,
    OperationalCaseSeverity,
    OperationalCaseStatus,
    OperationalCaseStatusCategory,
    OperationalCaseTimelineEvent,
    OperationalCaseType,
    SLA_STATUS_BREACHED,
    SLA_STATUS_MET,
    SLA_STATUS_NOT_APPLICABLE,
    SLA_STATUS_NOT_CONFIGURED,
    SLA_STATUS_PENDING,
    TimelineEventType,
    is_owner_facing_operational_case,
    operational_case_status_category,
    operational_case_system_status_transitions,
    operational_case_status_transitions,
)
from app.brain.operator_case_projections import is_case_degraded, latest_evidence_at, source_connectors

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
OperationalCaseSlaStatus = Literal["not_configured", "not_applicable", "pending", "breached", "met"]
OperationalCaseIssueTypeReleaseState = Literal[
    "promoted", "readiness_gated", "deferred", "internal_only"
]


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
    WorkItemQueryFieldDefinition(
        "owner_visible",
        "bool",
        allowed_operators=frozenset({"=", "!="}),
        facetable=True,
    ),
    WorkItemQueryFieldDefinition("assignee_ref", "string", facetable=True),
    WorkItemQueryFieldDefinition("case_type", "enum", frozenset(get_args(OperationalCaseType)), facetable=True),
    WorkItemQueryFieldDefinition("severity", "enum", frozenset(get_args(OperationalCaseSeverity)), facetable=True),
    WorkItemQueryFieldDefinition("priority_score", "int", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition("sla_target_seconds", "int", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition("due_at", "datetime", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition("latest_evidence_at", "datetime", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition("evidence_snapshot_count", "int", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition("evidence_source_count", "int", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition("comment_count", "int", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition("last_comment_at", "datetime", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition("timeline_event_count", "int", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition("last_event_at", "datetime", allowed_operators=_RANGE_OPERATORS, sortable=True),
    WorkItemQueryFieldDefinition(
        "last_event_type",
        "enum",
        frozenset(get_args(TimelineEventType)),
        facetable=True,
    ),
    WorkItemQueryFieldDefinition(
        "sla_status",
        "enum",
        frozenset(get_args(OperationalCaseSlaStatus)),
        facetable=True,
    ),
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

    Metric registration and owner-facing promotion are separate gates. Case
    families with ``CASE_FAMILY_METRICS`` evidence contracts are detectable, but
    only explicitly promoted families are eligible for owner-facing projections;
    registered families that still need source/readiness proof remain
    ``readiness_gated``.
    """

    if case_type in OWNER_FACING_OPERATIONAL_CASE_TYPES:
        return "promoted"
    if case_type in READINESS_GATED_OPERATIONAL_CASE_TYPES:
        return "readiness_gated"
    if case_type in get_args(OperationalCaseType):
        return "deferred"
    return "internal_only"


def case_status_category(case: OperationalCase) -> OperationalCaseStatusCategory:
    return operational_case_status_category(case.status)


def case_owner_visible(case: OperationalCase) -> bool:
    """Return whether a case instance can appear in owner-facing surfaces."""

    return is_owner_facing_operational_case(case)


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


def case_sla_status(case: OperationalCase, now: datetime | None = None) -> OperationalCaseSlaStatus:
    if case.due_at is None:
        return SLA_STATUS_NOT_CONFIGURED
    if case.status == "resolved":
        return SLA_STATUS_MET
    if case.status == "dismissed":
        return SLA_STATUS_NOT_APPLICABLE
    now = now or datetime.now(tz=timezone.utc)
    if now >= case.due_at:
        return SLA_STATUS_BREACHED
    return SLA_STATUS_PENDING


def allowed_priority_brackets() -> set[str]:
    return {definition.bracket for definition in _PRIORITY_DEFINITIONS}


def work_item_query_field_spec(field: str) -> WorkItemQueryFieldDefinition | None:
    """Return the canonical query field definition, if the field is allowlisted."""

    return _WORK_ITEM_QUERY_FIELD_BY_KEY.get(field)


def work_item_query_field_definition(field: str) -> dict[str, Any] | None:
    """Expose one canonical query-field definition for operator/query surfaces."""

    definition = work_item_query_field_spec(field)
    if definition is None:
        return None
    return {
        "field": definition.field,
        "value_type": definition.value_type,
        "allowed_values": sorted(definition.allowed_values) if definition.allowed_values is not None else None,
        "allowed_operators": sorted(definition.allowed_operators),
        "sortable": definition.sortable,
        "facetable": definition.facetable,
    }


def allowed_work_item_query_sort_fields() -> set[str]:
    """Return canonical fields allowed in JQL-lite ORDER BY clauses."""

    return {definition.field for definition in _WORK_ITEM_QUERY_FIELD_DEFINITIONS if definition.sortable}


def allowed_work_item_facet_fields() -> set[str]:
    """Return canonical WorkItem fields allowed for faceted operator counts."""

    return {definition.field for definition in _WORK_ITEM_QUERY_FIELD_DEFINITIONS if definition.facetable}


def work_item_query_field_definitions() -> list[dict[str, Any]]:
    """Expose canonical query-field metadata for tests/docs/operator surfaces."""

    definitions: list[dict[str, Any]] = []
    for definition in _WORK_ITEM_QUERY_FIELD_DEFINITIONS:
        serialized = work_item_query_field_definition(definition.field)
        if serialized is not None:
            definitions.append(serialized)
    return definitions


def case_work_item_id(case: OperationalCase) -> str:
    return f"{case_project_key(case)}:{case.case_id}"


def case_evidence_snapshot_ids(case: OperationalCase) -> list[str]:
    return [snapshot.snapshot_id for snapshot in case.evidence_snapshots]


def case_latest_evidence_at(case: OperationalCase) -> datetime | None:
    return latest_evidence_at(case)


def case_timeline_event_count(case: OperationalCase) -> int:
    return len(case.timeline)


def case_comment_count(case: OperationalCase) -> int:
    return sum(1 for event in case.timeline if event.event_type == "operator_comment")


def case_last_comment_at(case: OperationalCase) -> datetime | None:
    comment_events = [event.created_at for event in case.timeline if event.event_type == "operator_comment"]
    if not comment_events:
        return None
    return max(comment_events)


def case_last_event_at(case: OperationalCase) -> datetime | None:
    if not case.timeline:
        return None
    return max(event.created_at for event in case.timeline)


def case_last_event_type(case: OperationalCase) -> str | None:
    if not case.timeline:
        return None
    return max(case.timeline, key=lambda event: event.created_at).event_type


def case_source_connectors(case: OperationalCase) -> list[str]:
    return source_connectors(case)


def case_evidence_source_count(case: OperationalCase) -> int:
    return len(case_source_connectors(case))


def case_evidence_is_degraded(case: OperationalCase) -> bool:
    return is_case_degraded(case)


def case_work_item_projection(case: OperationalCase, now: datetime | None = None) -> dict[str, Any]:
    """Project an OperationalCase as a WorkItem-shaped API object."""

    return {
        "work_item_id": case_work_item_id(case),
        "project_key": case_project_key(case),
        "issue_type": case_issue_type(case),
        "release_state": case_type_release_state(case.case_type),
        "owner_visible": case_owner_visible(case),
        "status": case.status,
        "status_category": case_status_category(case),
        "priority_score": case.priority_score,
        "priority_bracket": case_priority_bracket(case),
        "sla_target_seconds": case.sla_target_seconds,
        "due_at": _iso_utc(case.due_at) if case.due_at is not None else None,
        "sla_status": case_sla_status(case, now=now),
        "assignee_ref": case.assignee_ref,
        "evidence_snapshot_ids": case_evidence_snapshot_ids(case),
        "evidence_snapshot_count": len(case.evidence_snapshots),
        "evidence_source_count": case_evidence_source_count(case),
        "source_connectors": case_source_connectors(case),
        "latest_evidence_at": _iso_utc(case_latest_evidence_at(case)) if case_latest_evidence_at(case) is not None else None,
        "degraded": case_evidence_is_degraded(case),
        "comment_count": case_comment_count(case),
        "last_comment_at": _iso_utc(case_last_comment_at(case)) if case_last_comment_at(case) is not None else None,
        "timeline_event_count": case_timeline_event_count(case),
        "last_event_at": _iso_utc(case_last_event_at(case)) if case_last_event_at(case) is not None else None,
        "last_event_type": case_last_event_type(case),
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

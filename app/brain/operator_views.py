"""Safe built-in case views and JQL-lite query support for operator surfaces.

This is intentionally a projection/query layer over Operational Cases. It does
not persist custom views and it never translates user input into SQL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.brain.operational_cases import (
    OperationalCase,
    OperationalCaseStore,
)
from app.brain.operator_api import OperatorAPIError, case_queue_item, parse_limit
from app.brain.operator_case_projections import is_case_degraded, latest_evidence_at, source_connectors
from app.brain.security.redaction import redact_secrets
from app.brain.work_items import (
    WorkItemQueryFieldDefinition,
    allowed_work_item_facet_fields,
    allowed_work_item_query_sort_fields,
    case_comment_count,
    case_issue_security_level,
    case_issue_type,
    case_last_comment_at,
    case_last_event_at,
    case_last_event_type,
    case_latest_reopened_at,
    case_owner_visible,
    case_priority_bracket,
    case_project_key,
    case_reopen_count,
    case_sla_elapsed_seconds,
    case_sla_remaining_seconds,
    case_sla_status,
    case_status_category,
    case_timeline_event_count,
    case_type_release_state,
    work_item_query_field_spec,
)

_MAX_JQL_LENGTH = 512
_MAX_CLAUSES = 8
_MAX_IN_VALUES = 20
_DEFAULT_SORT: tuple[tuple[str, str], ...] = (("priority_score", "DESC"), ("opened_at", "ASC"))
_ALLOWED_SORT_FIELDS = allowed_work_item_query_sort_fields()


@dataclass(frozen=True)
class CaseJQLClause:
    field: str
    operator: str
    values: tuple[Any, ...]


@dataclass(frozen=True)
class ParsedCaseJQL:
    raw: str
    clauses: tuple[CaseJQLClause, ...]
    order_by: tuple[tuple[str, str], ...]

    @property
    def normalized(self) -> str:
        clause_parts = []
        for clause in self.clauses:
            if clause.operator == "IN":
                values = ", ".join(_format_value(value) for value in clause.values)
                clause_parts.append(f"{clause.field} IN ({values})")
            else:
                clause_parts.append(f"{clause.field} {clause.operator} {_format_value(clause.values[0])}")
        order = ", ".join(f"{field} {direction}" for field, direction in self.order_by)
        if clause_parts:
            return f"{' AND '.join(clause_parts)} ORDER BY {order}"
        return f"ORDER BY {order}"


_BUILTIN_CASE_VIEWS: tuple[dict[str, Any], ...] = (
    {
        "view_id": "open_cases",
        "label": "Open cases",
        "description": "All currently open Operational Cases.",
        "jql": "status = open ORDER BY priority_score DESC",
        "readonly": True,
    },
    {
        "view_id": "acknowledged_cases",
        "label": "Acknowledged cases",
        "description": "Cases acknowledged by an operator, most recently updated first.",
        "jql": "status = acknowledged ORDER BY updated_at DESC",
        "readonly": True,
    },
    {
        "view_id": "in_progress_cases",
        "label": "In-progress cases",
        "description": "Cases actively being worked by an operator, most recently updated first.",
        "jql": "status = in_progress ORDER BY updated_at DESC",
        "readonly": True,
    },
    {
        "view_id": "resolved_cases",
        "label": "Resolved cases",
        "description": "Resolved cases, most recently updated first.",
        "jql": "status = resolved ORDER BY updated_at DESC",
        "readonly": True,
    },
    {
        "view_id": "critical_open",
        "label": "Critical open cases",
        "description": "Open critical cases first.",
        "jql": "status = open AND severity = critical ORDER BY priority_score DESC",
        "readonly": True,
    },
    {
        "view_id": "data_stale",
        "label": "Data stale",
        "description": "Open, acknowledged, or in-progress stale-data cases.",
        "jql": "case_type = data_stale AND status IN (open, acknowledged, in_progress) ORDER BY updated_at DESC",
        "readonly": True,
    },
    {
        "view_id": "stockout_risk",
        "label": "Stock risks",
        "description": "Open, acknowledged, or in-progress stockout risk cases.",
        "jql": "case_type = stockout_risk AND status IN (open, acknowledged, in_progress) ORDER BY priority_score DESC",
        "readonly": True,
    },
    {
        "view_id": "connector_degraded",
        "label": "Connector degraded",
        "description": "Actionable cases whose evidence is stale, degraded, or missing.",
        "jql": "status IN (open, acknowledged, in_progress) AND degraded = true ORDER BY updated_at DESC",
        "readonly": True,
    },
    {
        "view_id": "owner_visible_actionable",
        "label": "Owner-visible actionable cases",
        "description": "Actionable Operational Cases safe to include in owner-facing briefs.",
        "jql": (
            "status IN (open, acknowledged, in_progress) AND owner_visible = true "
            "ORDER BY priority_score DESC, opened_at ASC"
        ),
        "readonly": True,
    },
    {
        "view_id": "internal_only_actionable",
        "label": "Internal-only actionable cases",
        "description": "Actionable Operational Cases that should stay inside the operator console.",
        "jql": (
            "status IN (open, acknowledged, in_progress) AND owner_visible = false "
            "ORDER BY priority_score DESC, opened_at ASC"
        ),
        "readonly": True,
    },
)


def builtin_case_views() -> list[dict[str, Any]]:
    return redact_secrets([dict(view) for view in _BUILTIN_CASE_VIEWS])


def get_builtin_case_view(view_id: str) -> dict[str, Any]:
    for view in _BUILTIN_CASE_VIEWS:
        if view["view_id"] == view_id:
            return redact_secrets(dict(view))
    raise OperatorAPIError("case_view_not_found", "case view not found", status_code=404)


def parse_case_jql(jql: str | None) -> ParsedCaseJQL:
    raw = (jql or "").strip()
    if not raw:
        return ParsedCaseJQL(raw="", clauses=(), order_by=_DEFAULT_SORT)
    if len(raw) > _MAX_JQL_LENGTH:
        raise OperatorAPIError("jql_too_long", "JQL query is too long", status_code=400)
    if re.search(r"(;|--|/\*|\*/|\bOR\b|\bNOT\b|\bDROP\b|\bSELECT\b|\bUPDATE\b|\bDELETE\b)", raw, re.IGNORECASE):
        raise OperatorAPIError("invalid_jql", "JQL contains unsupported syntax", status_code=400)

    query_body, order_by = _split_order_by(raw)
    if "(" in query_body or ")" in query_body:
        # Parentheses are only allowed as part of an IN clause; parsing below will
        # accept those. This cheap check catches stray parentheses early.
        stripped_in = re.sub(r"\bIN\s*\([^)]*\)", "IN_LIST", query_body, flags=re.IGNORECASE)
        if "(" in stripped_in or ")" in stripped_in:
            raise OperatorAPIError("invalid_jql", "JQL parentheses are only supported for IN clauses", status_code=400)

    parts = [part.strip() for part in re.split(r"\s+AND\s+", query_body, flags=re.IGNORECASE) if part.strip()]
    if len(parts) > _MAX_CLAUSES:
        raise OperatorAPIError("jql_clause_limit_exceeded", "JQL clause limit exceeded", status_code=400)
    clauses = tuple(_parse_clause(part) for part in parts)
    return ParsedCaseJQL(raw=raw, clauses=clauses, order_by=order_by)


def query_case_queue(
    store: OperationalCaseStore,
    *,
    business_id: str,
    jql: str | None,
    limit: str | None,
    view: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    parsed = parse_case_jql(jql)
    parsed_limit = parse_limit(limit)
    candidates = store.list_cases(business_id=business_id, limit=None)
    filtered = [case for case in candidates if _matches(case, parsed.clauses, now=now)]
    total = len(filtered)
    filtered = _sort_cases(filtered, parsed.order_by, now=now)
    limited = filtered[:parsed_limit]
    data: dict[str, Any] = {
        "jql": parsed.raw,
        "normalized_jql": parsed.normalized,
        "cases": [case_queue_item(case, now=now) for case in limited],
        "limit": parsed_limit,
        "count": len(limited),
        "total": total,
        "truncated": total > len(limited),
    }
    if view is not None:
        data["view"] = {key: view[key] for key in ("view_id", "label", "readonly")}
    return redact_secrets(data)


def facet_case_queue(
    store: OperationalCaseStore,
    *,
    business_id: str,
    field: str | None,
    jql: str | None,
    limit: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return deterministic WorkItem field facets over route-scoped cases.

    Facets reuse the same allowlisted JQL parser and field registry as the case
    queue. The caller supplies business scope via the route; ``business_id`` is
    intentionally not a facetable/queryable field, preventing cross-tenant scope
    from becoming user-controlled query text.
    """

    facet_field = (field or "").strip()
    if facet_field not in allowed_work_item_facet_fields():
        label = facet_field or "[missing]"
        raise OperatorAPIError("unsupported_facet_field", f"Unsupported facet field: {label}", status_code=400)

    parsed = parse_case_jql(jql)
    bucket_limit = parse_limit(limit, default=20)
    candidates = store.list_cases(business_id=business_id, limit=None)
    filtered = [case for case in candidates if _matches(case, parsed.clauses, now=now)]
    counts: dict[Any, int] = {}
    for case in filtered:
        for value in _case_facet_values(case, facet_field, now=now):
            counts[value] = counts.get(value, 0) + 1

    buckets = [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], _facet_value_sort_key(item[0])))
    ]
    selected = buckets[:bucket_limit]
    data = {
        "field": facet_field,
        "jql": parsed.raw,
        "normalized_jql": parsed.normalized,
        "total_cases": len(filtered),
        "limit": bucket_limit,
        "returned": len(selected),
        "truncated": len(buckets) > len(selected),
        "buckets": selected,
    }
    return redact_secrets(data)


def _case_facet_values(case: OperationalCase, field: str, now: datetime | None = None) -> tuple[Any, ...]:
    if field == "source_connector":
        return tuple(_case_source_connectors(case))
    return (_case_field_value(case, field, now=now),)


def _facet_value_sort_key(value: Any) -> tuple[str, str]:
    if value is None:
        return ("1", "")
    if isinstance(value, bool):
        return ("0", "true" if value else "false")
    return ("0", str(value))


def _split_order_by(raw: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    match = re.search(r"\s+ORDER\s+BY\s+(.+)$", raw, flags=re.IGNORECASE)
    if not match:
        return raw, _DEFAULT_SORT
    body = raw[: match.start()].strip()
    order_text = match.group(1).strip()
    order_parts = [part.strip() for part in order_text.split(",") if part.strip()]
    if not order_parts:
        raise OperatorAPIError("invalid_jql", "ORDER BY requires at least one field", status_code=400)
    order: list[tuple[str, str]] = []
    for part in order_parts:
        order_match = re.fullmatch(r"([A-Za-z_.]+)\s+(ASC|DESC)", part, flags=re.IGNORECASE)
        if order_match is None:
            raise OperatorAPIError("invalid_jql", "ORDER BY entries must include field and direction", status_code=400)
        field = order_match.group(1)
        direction = order_match.group(2).upper()
        if field not in _ALLOWED_SORT_FIELDS:
            raise OperatorAPIError("unsupported_jql_field", f"Unsupported JQL sort field: {field}", status_code=400)
        order.append((field, direction))
    return body, tuple(order)


def _parse_clause(text: str) -> CaseJQLClause:
    in_match = re.fullmatch(r"([A-Za-z_.]+)\s+IN\s*\(([^)]*)\)", text, flags=re.IGNORECASE)
    if in_match is not None:
        field = in_match.group(1)
        raw_values = [value.strip() for value in in_match.group(2).split(",") if value.strip()]
        if not raw_values:
            raise OperatorAPIError("invalid_jql", "JQL IN clauses require at least one value", status_code=400)
        if len(raw_values) > _MAX_IN_VALUES:
            raise OperatorAPIError("jql_clause_limit_exceeded", "JQL IN value limit exceeded", status_code=400)
        spec = _field_spec(field)
        _ensure_operator(field, "IN", spec)
        return CaseJQLClause(field=field, operator="IN", values=tuple(_coerce_value(field, value, spec) for value in raw_values))

    match = re.fullmatch(r"([A-Za-z_.]+)\s*(=|!=|>=|<=|>|<)\s*(.+)", text)
    if match is None:
        raise OperatorAPIError("invalid_jql", "Invalid JQL clause", status_code=400)
    field, operator, raw_value = match.group(1), match.group(2), match.group(3).strip()
    spec = _field_spec(field)
    _ensure_operator(field, operator, spec)
    return CaseJQLClause(field=field, operator=operator, values=(_coerce_value(field, raw_value, spec),))


def _field_spec(field: str) -> WorkItemQueryFieldDefinition:
    spec = work_item_query_field_spec(field)
    if spec is None:
        raise OperatorAPIError("unsupported_jql_field", f"Unsupported JQL field: {field}", status_code=400)
    return spec


def _ensure_operator(field: str, operator: str, spec: WorkItemQueryFieldDefinition) -> None:
    if operator not in spec.allowed_operators:
        raise OperatorAPIError("unsupported_jql_operator", f"Unsupported operator for {field}: {operator}", status_code=400)


def _coerce_value(field: str, raw_value: str, spec: WorkItemQueryFieldDefinition) -> Any:
    value = _unquote(raw_value.strip())
    if not re.fullmatch(r"[A-Za-z0-9_:\-+.]+", value):
        raise OperatorAPIError("invalid_jql", "JQL value contains unsupported characters", status_code=400)
    if spec.value_type == "enum":
        if spec.allowed_values is not None and value not in spec.allowed_values:
            raise OperatorAPIError("unsupported_jql_value", f"Unsupported value for {field}: {value}", status_code=400)
        return value
    if spec.value_type == "int":
        try:
            parsed = int(value)
        except ValueError as exc:
            raise OperatorAPIError("unsupported_jql_value", f"Expected integer for {field}", status_code=400) from exc
        return parsed
    if spec.value_type == "datetime":
        try:
            parsed_dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise OperatorAPIError("unsupported_jql_value", f"Expected ISO datetime for {field}", status_code=400) from exc
        if parsed_dt.tzinfo is None or parsed_dt.utcoffset() is None:
            raise OperatorAPIError("unsupported_jql_value", f"Expected timezone-aware ISO datetime for {field}", status_code=400)
        return parsed_dt
    if spec.value_type == "bool":
        if value not in {"true", "false"}:
            raise OperatorAPIError("unsupported_jql_value", f"Expected boolean for {field}", status_code=400)
        return value == "true"
    return value


def _unquote(value: str) -> str:
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def _format_value(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _matches(case: OperationalCase, clauses: tuple[CaseJQLClause, ...], now: datetime | None = None) -> bool:
    return all(_matches_clause(case, clause, now=now) for clause in clauses)


def _matches_clause(case: OperationalCase, clause: CaseJQLClause, now: datetime | None = None) -> bool:
    if clause.field == "source_connector":
        return _matches_source_connector(case, clause)

    actual = _case_field_value(case, clause.field, now=now)
    if clause.operator == "IN":
        return actual in clause.values
    expected = clause.values[0]
    if clause.operator == "=":
        return actual == expected
    if clause.operator == "!=":
        return actual != expected
    if actual is None:
        return False
    if clause.operator == ">":
        return actual > expected
    if clause.operator == ">=":
        return actual >= expected
    if clause.operator == "<":
        return actual < expected
    if clause.operator == "<=":
        return actual <= expected
    raise OperatorAPIError("unsupported_jql_operator", f"Unsupported operator: {clause.operator}", status_code=400)


def _case_source_connectors(case: OperationalCase) -> tuple[str, ...]:
    return tuple(source_connectors(case))


def _matches_source_connector(case: OperationalCase, clause: CaseJQLClause) -> bool:
    sources = _case_source_connectors(case)
    if clause.operator == "IN":
        return any(source in clause.values for source in sources)
    expected = clause.values[0]
    if clause.operator == "=":
        return expected in sources
    if clause.operator == "!=":
        return expected not in sources
    raise OperatorAPIError("unsupported_jql_operator", f"Unsupported operator: {clause.operator}", status_code=400)


def _case_field_value(case: OperationalCase, field: str, now: datetime | None = None) -> Any:
    if field == "entity.kind":
        return case.entity_scope.get("kind")
    if field == "entity.id":
        return case.entity_scope.get("id")
    if field == "entity.label":
        return case.entity_scope.get("label")
    if field == "degraded":
        return is_case_degraded(case)
    if field == "latest_evidence_at":
        return latest_evidence_at(case)
    if field == "evidence_snapshot_count":
        return len(case.evidence_snapshots)
    if field == "evidence_source_count":
        return len(_case_source_connectors(case))
    if field == "comment_count":
        return case_comment_count(case)
    if field == "reopen_count":
        return case_reopen_count(case)
    if field == "last_comment_at":
        return case_last_comment_at(case)
    if field == "latest_reopened_at":
        return case_latest_reopened_at(case)
    if field == "timeline_event_count":
        return case_timeline_event_count(case)
    if field == "last_event_at":
        return case_last_event_at(case)
    if field == "last_event_type":
        return case_last_event_type(case)
    if field == "project":
        return case_project_key(case)
    if field == "issue_type":
        return case_issue_type(case)
    if field == "release_state":
        return case_type_release_state(case.case_type)
    if field == "owner_visible":
        return case_owner_visible(case)
    if field == "issue_security_level":
        return case_issue_security_level(case)
    if field == "status_category":
        return case_status_category(case)
    if field == "priority_bracket":
        return case_priority_bracket(case)
    if field == "sla_elapsed_seconds":
        return case_sla_elapsed_seconds(case, now=now)
    if field == "sla_remaining_seconds":
        return case_sla_remaining_seconds(case, now=now)
    if field == "sla_status":
        return case_sla_status(case, now=now)
    return getattr(case, field)


def _sort_cases(cases: list[OperationalCase], order_by: tuple[tuple[str, str], ...], now: datetime | None = None) -> list[OperationalCase]:
    result = list(cases)
    # Apply stable sorts from last to first so mixed directions work.
    # Missing values stay at the end for both ASC and DESC sorts.
    for field, direction in reversed(order_by + (("case_id", "ASC"),)):
        reverse = direction == "DESC"
        present: list[tuple[Any, OperationalCase]] = []
        missing: list[OperationalCase] = []
        for case in result:
            value = _sort_value(case, field, now=now)
            if value is None:
                missing.append(case)
            else:
                present.append((value, case))
        present.sort(key=lambda item: item[0], reverse=reverse)
        result = [case for _value, case in present] + missing
    return result


def _sort_value(case: OperationalCase, field: str, now: datetime | None = None) -> Any:
    if field == "case_id":
        return case.case_id
    return _case_field_value(case, field, now=now)

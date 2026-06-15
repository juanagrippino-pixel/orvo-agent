"""Safe built-in case views and JQL-lite query support for operator surfaces.

This is intentionally a projection/query layer over Operational Cases. It does
not persist custom views and it never translates user input into SQL.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import Any

from app.brain.operational_cases import (
    OperationalCase,
    OperationalCaseStore,
)
from app.brain.operator_api import OperatorAPIError, case_queue_item, parse_case_status, parse_limit
from app.brain.operator_api.common import case_reopen_stats
from app.brain.operator_case_projections import is_case_degraded, source_connectors
from app.brain.security.redaction import redact_secrets, redact_text
from app.brain.work_items import (
    WorkItemQueryFieldDefinition,
    allowed_work_item_facet_fields,
    allowed_work_item_query_sort_fields,
    case_evidence_snapshot_count,
    case_issue_type,
    case_latest_evidence_at,
    case_priority_bracket,
    case_project_key,
    case_status_category,
    case_type_release_state,
    work_item_query_field_definitions,
    work_item_query_field_spec,
)

_MAX_JQL_LENGTH = 512
_MAX_CLAUSES = 8
_MAX_IN_VALUES = 20
_DEFAULT_SORT: tuple[tuple[str, str], ...] = (("priority_score", "DESC"), ("opened_at", "ASC"))
_ALLOWED_SORT_FIELDS = allowed_work_item_query_sort_fields()
_CASE_EXPORT_COLUMNS: tuple[str, ...] = (
    "case_id",
    "business_id",
    "work_item_id",
    "case_type",
    "issue_type",
    "release_state",
    "title",
    "status",
    "status_category",
    "severity",
    "priority_score",
    "priority_bracket",
    "opened_at",
    "updated_at",
    "acknowledged_at",
    "resolved_at",
    "assignee_ref",
    "latest_run_id",
    "evidence_snapshot_count",
    "latest_evidence_at",
    "source_connectors",
    "degraded",
)
_CASE_EXPORT_FORMATS = {"csv"}


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
        "description": "Cases acknowledged by an operator, ordered by the canonical acknowledged_at timestamp.",
        "jql": "status = acknowledged ORDER BY acknowledged_at DESC",
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
        "view_id": "recently_resolved",
        "label": "Recently resolved",
        "description": "Resolved cases ordered by the canonical resolved_at timestamp.",
        "jql": "status = resolved ORDER BY resolved_at DESC",
        "readonly": True,
    },
    {
        "view_id": "recently_reopened",
        "label": "Recently reopened",
        "description": "Actionable cases reopened after resolution, ordered by latest recurrence time.",
        "jql": "status IN (open, acknowledged, in_progress) AND reopen_count >= 1 ORDER BY latest_reopened_at DESC",
        "readonly": True,
    },
    {
        "view_id": "high_priority",
        "label": "High priority",
        "description": "Actionable high-priority cases ordered by priority score.",
        "jql": "status IN (open, acknowledged, in_progress) AND priority_bracket = high ORDER BY priority_score DESC",
        "readonly": True,
    },
    {
        "view_id": "evidence_backed_actionable",
        "label": "Evidence-backed actionable",
        "description": "Actionable cases with canonical evidence snapshots, ordered by latest evidence freshness.",
        "jql": "status IN (open, acknowledged, in_progress) AND evidence_snapshot_count > 0 ORDER BY latest_evidence_at DESC",
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
)


def _builtin_view_query_metadata(jql: str) -> dict[str, Any]:
    parsed = parse_case_jql(jql)
    return {
        "normalized_jql": parsed.normalized,
        "filter_fields": sorted({clause.field for clause in parsed.clauses}),
        "sort_fields": [field for field, _direction in parsed.order_by],
    }


def _annotated_builtin_case_view(view: dict[str, Any]) -> dict[str, Any]:
    annotated = dict(view)
    annotated.update(_builtin_view_query_metadata(view["jql"]))
    return annotated


def builtin_case_views() -> list[dict[str, Any]]:
    return redact_secrets([_annotated_builtin_case_view(view) for view in _BUILTIN_CASE_VIEWS])


def get_builtin_case_view(view_id: str) -> dict[str, Any]:
    for view in _BUILTIN_CASE_VIEWS:
        if view["view_id"] == view_id:
            return redact_secrets(_annotated_builtin_case_view(view))
    raise OperatorAPIError("case_view_not_found", "case view not found", status_code=404)


def list_case_query_fields() -> dict[str, Any]:
    """Return canonical read-only WorkItem query metadata for operator surfaces."""

    return redact_secrets(
        {
            "readonly": True,
            "fields_by_name": {definition["field"]: definition for definition in work_item_query_field_definitions()},
            "sort_fields": sorted(_ALLOWED_SORT_FIELDS),
            "facet_fields": sorted(allowed_work_item_facet_fields()),
        }
    )


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
) -> dict[str, Any]:
    parsed = parse_case_jql(jql)
    parsed_limit = parse_limit(limit)
    candidates = store.list_cases(business_id=business_id, limit=None)
    filtered = [case for case in candidates if _matches(case, parsed.clauses)]
    total = len(filtered)
    filtered = _sort_cases(filtered, parsed.order_by)
    limited = filtered[:parsed_limit]
    data: dict[str, Any] = {
        "view_id": view.get("view_id") if view is not None else None,
        "jql": parsed.raw,
        "normalized_jql": parsed.normalized,
        "cases": [case_queue_item(case) for case in limited],
        "limit": parsed_limit,
        "count": len(limited),
        "total": total,
        "truncated": total > len(limited),
    }
    if view is not None:
        data["view"] = {key: view[key] for key in ("view_id", "label", "readonly")}
    return redact_secrets(data)


def export_case_queue_csv(
    store: OperationalCaseStore,
    *,
    business_id: str,
    view_id: str | None = None,
    jql: str | None = None,
    status: str | None = None,
    limit: str | None = None,
    export_format: str = "csv",
) -> dict[str, Any]:
    """Return a redacted CSV export for a route-scoped case queue.

    This is a read-only projection over ``OperationalCase`` state. It reuses the
    same allowlisted JQL parser, status parser, limit guard, and WorkItem
    projections as the JSON case queue so exports cannot become an alternate
    source of truth or a second query language.
    """

    export_format = (export_format or "csv").strip().lower()
    if export_format not in _CASE_EXPORT_FORMATS:
        raise OperatorAPIError("invalid_export_format", f"Unsupported export format: {export_format}", status_code=400)

    selected_filters = [
        filter_name
        for filter_name, filter_value in (("view_id", view_id), ("status", status), ("jql", jql))
        if filter_value not in (None, "")
    ]
    if len(selected_filters) > 1:
        raise OperatorAPIError(
            "conflicting_case_filters",
            "view_id, status, and jql filters are mutually exclusive",
            status_code=400,
        )

    if view_id not in (None, ""):
        view = get_builtin_case_view(str(view_id).strip())
        queue = query_case_queue(store, business_id=business_id, jql=view["jql"], limit=limit, view=view)
        rows = [_case_export_row(item) for item in queue["cases"]]
    elif jql not in (None, ""):
        queue = query_case_queue(store, business_id=business_id, jql=jql, limit=limit)
        rows = [_case_export_row(item) for item in queue["cases"]]
    else:
        parsed_status = parse_case_status(status)
        parsed_limit = parse_limit(limit)
        cases = store.list_cases(business_id=business_id, status=parsed_status, limit=parsed_limit)
        rows = [_case_export_row(case_queue_item(case)) for case in cases]

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=_CASE_EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return redact_secrets(
        {
            "content_type": "text/csv; charset=utf-8",
            "filename": _case_export_filename(business_id),
            "body": output.getvalue(),
        }
    )


def facet_case_queue(
    store: OperationalCaseStore,
    *,
    business_id: str,
    field: str | None,
    view_id: str | None,
    jql: str | None,
    limit: str | None,
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

    selected_view: dict[str, Any] | None = None
    selected_jql = jql
    if view_id not in (None, ""):
        if jql not in (None, ""):
            raise OperatorAPIError(
                "conflicting_case_filters",
                "view_id and jql filters are mutually exclusive",
                status_code=400,
            )
        selected_view = get_builtin_case_view(str(view_id).strip())
        selected_jql = selected_view["jql"]

    parsed = parse_case_jql(selected_jql)
    bucket_limit = parse_limit(limit, default=20)
    candidates = store.list_cases(business_id=business_id, limit=None)
    filtered = [case for case in candidates if _matches(case, parsed.clauses)]
    counts: dict[Any, int] = {}
    for case in filtered:
        for value in _case_facet_values(case, facet_field):
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
    if selected_view is not None:
        data["view_id"] = selected_view["view_id"]
        data["view"] = {key: selected_view[key] for key in ("view_id", "label", "readonly")}
    return redact_secrets(data)


def _case_facet_values(case: OperationalCase, field: str) -> tuple[Any, ...]:
    if field == "source_connector":
        return tuple(_case_source_connectors(case))
    return (_case_field_value(case, field),)


def _facet_value_sort_key(value: Any) -> tuple[str, str]:
    if value is None:
        return ("1", "")
    if isinstance(value, bool):
        return ("0", "true" if value else "false")
    return ("0", str(value))


def _case_export_row(item: dict[str, Any]) -> dict[str, Any]:
    work_item = item.get("work_item") or {}
    source_connectors = item.get("source_connectors") or []
    if isinstance(source_connectors, list):
        source_text = "|".join(str(value) for value in source_connectors)
    else:
        source_text = str(source_connectors)
    return {
        "case_id": item.get("case_id"),
        "business_id": item.get("business_id"),
        "work_item_id": work_item.get("work_item_id"),
        "case_type": item.get("case_type"),
        "issue_type": work_item.get("issue_type"),
        "release_state": work_item.get("release_state"),
        "title": item.get("title"),
        "status": item.get("status"),
        "status_category": work_item.get("status_category"),
        "severity": item.get("severity"),
        "priority_score": item.get("priority_score"),
        "priority_bracket": work_item.get("priority_bracket"),
        "opened_at": item.get("opened_at"),
        "updated_at": item.get("updated_at"),
        "acknowledged_at": item.get("acknowledged_at"),
        "resolved_at": item.get("resolved_at"),
        "assignee_ref": item.get("assignee_ref"),
        "latest_run_id": item.get("latest_run_id"),
        "evidence_snapshot_count": item.get("evidence_snapshot_count"),
        "latest_evidence_at": item.get("latest_evidence_at"),
        "source_connectors": source_text,
        "degraded": "true" if item.get("degraded") else "false",
    }


def _case_export_filename(business_id: str) -> str:
    redacted = redact_text(business_id) or "business"
    if redacted != business_id:
        token = "redacted"
    else:
        token = re.sub(r"[^A-Za-z0-9_.-]+", "_", business_id).strip("._") or "business"
    return f"{token}_cases.csv"


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
    raw_value = raw_value.strip()
    quoted = _is_quoted(raw_value)
    value = _unquote(raw_value)
    if quoted:
        if not _is_safe_quoted_string(value):
            raise OperatorAPIError("invalid_jql", "JQL value contains unsupported characters", status_code=400)
    elif not re.fullmatch(r"[A-Za-z0-9_:\-+.]+", value):
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


def _is_quoted(value: str) -> bool:
    return (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'"))


def _is_safe_quoted_string(value: str) -> bool:
    return bool(value) and re.fullmatch(r"[^\x00-\x1F\x7F\"'<>;]+", value) is not None


def _format_value(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _matches(case: OperationalCase, clauses: tuple[CaseJQLClause, ...]) -> bool:
    return all(_matches_clause(case, clause) for clause in clauses)


def _matches_clause(case: OperationalCase, clause: CaseJQLClause) -> bool:
    if clause.field == "source_connector":
        return _matches_source_connector(case, clause)

    actual = _case_field_value(case, clause.field)
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


def _case_field_value(case: OperationalCase, field: str) -> Any:
    if field == "entity.kind":
        return case.entity_scope.get("kind")
    if field == "entity.id":
        return case.entity_scope.get("id")
    if field == "entity.label":
        return case.entity_scope.get("label")
    if field == "degraded":
        return is_case_degraded(case)
    if field == "project":
        return case_project_key(case)
    if field == "issue_type":
        return case_issue_type(case)
    if field == "release_state":
        return case_type_release_state(case.case_type)
    if field == "status_category":
        return case_status_category(case)
    if field == "priority_bracket":
        return case_priority_bracket(case)
    if field == "evidence_snapshot_count":
        return case_evidence_snapshot_count(case)
    if field == "latest_evidence_at":
        return case_latest_evidence_at(case)
    if field in {"reopen_count", "latest_reopened_at"}:
        reopen_count, latest_reopened_at = case_reopen_stats(case)
        if field == "reopen_count":
            return reopen_count
        return latest_reopened_at
    return getattr(case, field)


def _sort_cases(cases: list[OperationalCase], order_by: tuple[tuple[str, str], ...]) -> list[OperationalCase]:
    result = list(cases)
    # Apply stable sorts from last to first so mixed directions work.
    for field, direction in reversed(order_by + (("case_id", "ASC"),)):
        reverse = direction == "DESC"
        result.sort(
            key=lambda case, sort_field=field, sort_direction=direction: _sort_value(
                case, sort_field, sort_direction
            ),
            reverse=reverse,
        )
    return result


def _sort_value(case: OperationalCase, field: str, direction: str) -> tuple[int, Any]:
    if field == "case_id":
        return (0, case.case_id)
    value = _case_field_value(case, field)
    if value is None:
        return (0, "") if direction == "DESC" else (1, "")
    return (1, value) if direction == "DESC" else (0, value)

"""Safe built-in case views and JQL-lite query support for operator surfaces.

This is intentionally a projection/query layer over Operational Cases. It does
not persist custom views and it never translates user input into SQL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, get_args

from app.brain.operational_cases import (
    OperationalCase,
    OperationalCaseSeverity,
    OperationalCaseStatus,
    OperationalCaseStore,
    OperationalCaseType,
)
from app.brain.operator_api import OperatorAPIError, case_queue_item, parse_limit
from app.brain.operator_case_projections import is_case_degraded, source_connectors
from app.brain.security.redaction import redact_secrets

_MAX_JQL_LENGTH = 512
_MAX_CLAUSES = 8
_MAX_IN_VALUES = 20
_DEFAULT_SORT: tuple[tuple[str, str], ...] = (("priority_score", "DESC"), ("opened_at", "ASC"))
_ALLOWED_SORT_FIELDS = {"priority_score", "opened_at", "updated_at"}
_ALLOWED_STATUS = set(get_args(OperationalCaseStatus))
_ALLOWED_CASE_TYPES = set(get_args(OperationalCaseType))
_ALLOWED_SEVERITY = set(get_args(OperationalCaseSeverity))

FieldType = Literal["bool", "enum", "int", "string", "datetime"]


@dataclass(frozen=True)
class FieldSpec:
    value_type: FieldType
    allowed_values: set[str] | None = None
    allowed_operators: frozenset[str] = frozenset({"=", "!=", "IN"})


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


_FIELD_SPECS: dict[str, FieldSpec] = {
    "status": FieldSpec("enum", _ALLOWED_STATUS),
    "case_type": FieldSpec("enum", _ALLOWED_CASE_TYPES),
    "severity": FieldSpec("enum", _ALLOWED_SEVERITY),
    "priority_score": FieldSpec("int", None, frozenset({"=", "!=", ">", ">=", "<", "<="})),
    "entity.kind": FieldSpec("string"),
    "entity.id": FieldSpec("string"),
    "entity.label": FieldSpec("string", None, frozenset({"=", "!="})),
    "latest_run_id": FieldSpec("string"),
    "source_connector": FieldSpec("string"),
    "degraded": FieldSpec("bool", None, frozenset({"=", "!="})),
    "assigned": FieldSpec("bool", None, frozenset({"=", "!="})),
    "dedupe_key": FieldSpec("string", None, frozenset({"=", "!="})),
    "opened_at": FieldSpec("datetime", None, frozenset({"=", "!=", ">", ">=", "<", "<="})),
    "updated_at": FieldSpec("datetime", None, frozenset({"=", "!=", ">", ">=", "<", "<="})),
    "resolved_at": FieldSpec("datetime", None, frozenset({"=", "!=", ">", ">=", "<", "<="})),
}


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
        "view_id": "unassigned_actionable",
        "label": "Unassigned actionable cases",
        "description": "Open, acknowledged, or in-progress cases without an assigned operator.",
        "jql": "status IN (open, acknowledged, in_progress) AND assigned = false ORDER BY priority_score DESC",
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
) -> dict[str, Any]:
    parsed = parse_case_jql(jql)
    parsed_limit = parse_limit(limit)
    candidates = store.list_cases(business_id=business_id, limit=None)
    filtered = [case for case in candidates if _matches(case, parsed.clauses)]
    total = len(filtered)
    filtered = _sort_cases(filtered, parsed.order_by)
    limited = filtered[:parsed_limit]
    data: dict[str, Any] = {
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


def summarize_builtin_case_view_totals(store: OperationalCaseStore, *, business_id: str) -> dict[str, Any]:
    """Return scoped counts for each built-in read-only case view.

    This dashboard primitive compiles every built-in view through the same
    JQL-lite parser used by executable case views, then counts matches against
    the business-scoped case set. It intentionally returns totals only, not raw
    cases, so dashboards can show saved-view coverage without making the
    dashboard a source of truth for queue state.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    views: list[dict[str, Any]] = []
    for view in _BUILTIN_CASE_VIEWS:
        parsed = parse_case_jql(view["jql"])
        total = sum(1 for case in cases if _matches(case, parsed.clauses))
        views.append(
            {
                "view_id": view["view_id"],
                "label": view["label"],
                "readonly": view["readonly"],
                "jql": view["jql"],
                "normalized_jql": parsed.normalized,
                "total": total,
            }
        )
    return redact_secrets({"business_id": business_id, "views": views})


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


def _field_spec(field: str) -> FieldSpec:
    spec = _FIELD_SPECS.get(field)
    if spec is None:
        raise OperatorAPIError("unsupported_jql_field", f"Unsupported JQL field: {field}", status_code=400)
    return spec


def _ensure_operator(field: str, operator: str, spec: FieldSpec) -> None:
    if operator not in spec.allowed_operators:
        raise OperatorAPIError("unsupported_jql_operator", f"Unsupported operator for {field}: {operator}", status_code=400)


def _coerce_value(field: str, raw_value: str, spec: FieldSpec) -> Any:
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
    if field == "assigned":
        return case.assignee_ref is not None
    return getattr(case, field)


def _sort_cases(cases: list[OperationalCase], order_by: tuple[tuple[str, str], ...]) -> list[OperationalCase]:
    result = list(cases)
    # Apply stable sorts from last to first so mixed directions work.
    for field, direction in reversed(order_by + (("case_id", "ASC"),)):
        reverse = direction == "DESC"
        result.sort(key=lambda case, sort_field=field: _sort_value(case, sort_field), reverse=reverse)
    return result


def _sort_value(case: OperationalCase, field: str) -> Any:
    if field == "case_id":
        return case.case_id
    return _case_field_value(case, field)

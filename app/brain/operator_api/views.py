from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403
from .cases import *  # noqa: F401,F403
from .top_cases import *  # noqa: F401,F403
from .recent_cases import *  # noqa: F401,F403
from .workflow import *  # noqa: F401,F403
from .histograms_resolution import *  # noqa: F401,F403
from .histograms_ack import *  # noqa: F401,F403


def parse_include_totals(value: str | None) -> bool:
    if value in (None, ""):
        return False
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise OperatorAPIError("invalid_include_totals", "include_totals must be true or false", status_code=400)


def list_builtin_case_views(
    store: OperationalCaseStore | None = None,
    *,
    business_id: str | None = None,
    include_totals: str | None = None,
) -> dict[str, Any]:
    from app.brain.operator_views import builtin_case_views, summarize_builtin_case_view_totals

    should_include_totals = parse_include_totals(include_totals)
    if not should_include_totals:
        return {"views": builtin_case_views(), "include_totals": False}
    if store is None or business_id is None:
        raise OperatorAPIError("missing_case_view_scope", "case view totals require business scope", status_code=400)
    data = summarize_builtin_case_view_totals(store, business_id=business_id)
    data["include_totals"] = True
    return data


def describe_case_query_fields() -> dict[str, Any]:
    """Expose the canonical read-only case query field registry for operator UIs.

    Tenant/business scope remains owned by the route and auth context, not by
    caller-supplied JQL. This keeps UI autocomplete and saved-view builders tied
    to the same allowlist used by parser/execution paths without introducing a
    second query vocabulary.
    """

    from app.brain.work_items import (
        allowed_case_query_sort_fields,
        operational_case_query_field_definitions,
    )

    return {
        "readonly": True,
        "scope": {
            "business_scope_source": "route",
            "query_controlled_business_scope": False,
        },
        "fields": operational_case_query_field_definitions(),
        "sort_fields": sorted(allowed_case_query_sort_fields()),
    }


def execute_builtin_case_view(
    store: OperationalCaseStore,
    *,
    business_id: str,
    view_id: str,
    limit: str | None,
) -> dict[str, Any]:
    from app.brain.operator_views import get_builtin_case_view, query_case_queue

    view = get_builtin_case_view(view_id)
    return query_case_queue(store, business_id=business_id, jql=view["jql"], limit=limit, view=view)


def list_case_facets(
    store: OperationalCaseStore,
    *,
    business_id: str,
    field: str | None,
    jql: str | None,
    limit: str | None,
) -> dict[str, Any]:
    from app.brain.operator_views import facet_case_queue

    return facet_case_queue(store, business_id=business_id, field=field, jql=jql, limit=limit)


def export_builtin_case_view(
    store: OperationalCaseStore,
    *,
    business_id: str,
    view_id: str,
    limit: str | None,
) -> dict[str, Any]:
    from app.brain.operator_views import export_builtin_case_view_rows

    return export_builtin_case_view_rows(store, business_id=business_id, view_id=view_id, limit=limit)


def summarize_case_view(
    store: OperationalCaseStore,
    *,
    business_id: str,
    view_id: str,
) -> dict[str, Any]:
    from app.brain.operator_views import summarize_builtin_case_view

    return summarize_builtin_case_view(store, business_id=business_id, view_id=view_id)


def summarize_case_query(
    store: OperationalCaseStore,
    *,
    business_id: str,
    jql: str | None,
) -> dict[str, Any]:
    from app.brain.operator_views import summarize_case_query_facets

    return summarize_case_query_facets(store, business_id=business_id, jql=jql)


__all__ = [name for name in globals() if not name.startswith("__")]

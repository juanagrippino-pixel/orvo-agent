from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403
from .cases import *  # noqa: F401,F403
from .top_cases import *  # noqa: F401,F403
from .recent_cases import *  # noqa: F401,F403
from .workflow import *  # noqa: F401,F403
from .histograms_resolution import *  # noqa: F401,F403
from .histograms_ack import *  # noqa: F401,F403


def list_builtin_case_views(
    store: OperationalCaseStore,
    *,
    business_id: str,
) -> dict[str, Any]:
    from app.brain.operator_views import builtin_case_views_with_counts

    return {"views": builtin_case_views_with_counts(store, business_id=business_id)}


def get_builtin_case_view_detail(
    store: OperationalCaseStore,
    *,
    business_id: str,
    view_id: str,
) -> dict[str, Any]:
    from app.brain.operator_views import describe_builtin_case_view

    return {"view": describe_builtin_case_view(store, business_id=business_id, view_id=view_id)}


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



def list_case_query_fields(*, field: str | None) -> dict[str, Any]:
    from app.brain.work_items import work_item_query_field_definition, work_item_query_field_definitions

    requested_field = (field or "").strip()
    if not requested_field:
        return {"fields": work_item_query_field_definitions()}

    definition = work_item_query_field_definition(requested_field)
    if definition is None:
        raise OperatorAPIError("unsupported_jql_field", f"Unsupported JQL field: {requested_field}", status_code=400)
    return {"field": definition}


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

__all__ = [name for name in globals() if not name.startswith("__")]

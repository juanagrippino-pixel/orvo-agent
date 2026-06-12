from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403
from .cases import *  # noqa: F401,F403
from .top_cases import *  # noqa: F401,F403
from .recent_cases import *  # noqa: F401,F403
from .workflow import *  # noqa: F401,F403
from .histograms_resolution import *  # noqa: F401,F403
from .histograms_ack import *  # noqa: F401,F403


def list_builtin_case_views() -> dict[str, Any]:
    from app.brain.operator_views import builtin_case_views

    return {"views": builtin_case_views()}


def get_builtin_case_view_detail(view_id: str) -> dict[str, Any]:
    from app.brain.operator_views import get_builtin_case_view

    return get_builtin_case_view(view_id)


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


def list_case_query_fields(field: str | None = None) -> dict[str, Any]:
    if field is not None and field.strip():
        from app.brain.work_items import work_item_query_field_definition

        definition = work_item_query_field_definition(field.strip())
        if definition is None:
            label = field.strip() or "[missing]"
            raise OperatorAPIError("unsupported_jql_field", f"Unsupported case query field: {label}", status_code=400)
        return definition

    from app.brain.operator_views import list_case_query_fields as fields

    return fields()


def list_case_facets(
    store: OperationalCaseStore,
    *,
    business_id: str,
    field: str | None,
    view_id: str | None,
    jql: str | None,
    limit: str | None,
) -> dict[str, Any]:
    from app.brain.operator_views import facet_case_queue

    return facet_case_queue(
        store,
        business_id=business_id,
        field=field,
        view_id=view_id,
        jql=jql,
        limit=limit,
    )


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
    from app.brain.operator_views import export_case_queue_csv as export

    return export(
        store,
        business_id=business_id,
        view_id=view_id,
        jql=jql,
        status=status,
        limit=limit,
        export_format=export_format,
    )



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
    from app.brain.operator_views import export_case_queue_csv as export

    return export(
        store,
        business_id=business_id,
        view_id=view_id,
        jql=jql,
        status=status,
        limit=limit,
        export_format=export_format,
    )



def export_case_queue_csv(
    store: OperationalCaseStore,
    *,
    business_id: str,
    jql: str | None = None,
    status: str | None = None,
    limit: str | None = None,
    export_format: str = "csv",
) -> dict[str, Any]:
    from app.brain.operator_views import export_case_queue_csv as export

    return export(
        store,
        business_id=business_id,
        jql=jql,
        status=status,
        limit=limit,
        export_format=export_format,
    )



def export_case_queue_csv(
    store: OperationalCaseStore,
    *,
    business_id: str,
    jql: str | None = None,
    status: str | None = None,
    limit: str | None = None,
    export_format: str = "csv",
) -> dict[str, Any]:
    from app.brain.operator_views import export_case_queue_csv as export

    return export(
        store,
        business_id=business_id,
        jql=jql,
        status=status,
        limit=limit,
        export_format=export_format,
    )



def export_case_queue_csv(
    store: OperationalCaseStore,
    *,
    business_id: str,
    jql: str | None = None,
    status: str | None = None,
    limit: str | None = None,
    export_format: str = "csv",
) -> dict[str, Any]:
    from app.brain.operator_views import export_case_queue_csv as export

    return export(
        store,
        business_id=business_id,
        jql=jql,
        status=status,
        limit=limit,
        export_format=export_format,
    )



def export_case_queue_csv(
    store: OperationalCaseStore,
    *,
    business_id: str,
    jql: str | None = None,
    status: str | None = None,
    limit: str | None = None,
    export_format: str = "csv",
) -> dict[str, Any]:
    from app.brain.operator_views import export_case_queue_csv as export

    return export(
        store,
        business_id=business_id,
        jql=jql,
        status=status,
        limit=limit,
        export_format=export_format,
    )


__all__ = [name for name in globals() if not name.startswith("__")]

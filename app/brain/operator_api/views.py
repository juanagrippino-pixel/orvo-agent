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

def execute_builtin_case_view(
    store: OperationalCaseStore,
    *,
    business_id: str,
    view_id: str,
    limit: str | None,
    as_of: str | None = None,
) -> dict[str, Any]:
    from app.brain.operator_views import get_builtin_case_view, query_case_queue

    view = get_builtin_case_view(view_id)
    return query_case_queue(store, business_id=business_id, jql=view["jql"], limit=limit, view=view, now=parse_case_as_of(as_of))


def list_case_facets(
    store: OperationalCaseStore,
    *,
    business_id: str,
    field: str | None,
    jql: str | None,
    limit: str | None,
    as_of: str | None = None,
) -> dict[str, Any]:
    from app.brain.operator_views import facet_case_queue

    return facet_case_queue(store, business_id=business_id, field=field, jql=jql, limit=limit, now=parse_case_as_of(as_of))

__all__ = [name for name in globals() if not name.startswith("__")]

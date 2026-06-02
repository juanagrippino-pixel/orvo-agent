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


def export_builtin_case_view(
    store: OperationalCaseStore,
    *,
    business_id: str,
    view_id: str,
    limit: str | None,
) -> dict[str, Any]:
    from app.brain.operator_views import export_builtin_case_view_rows

    return export_builtin_case_view_rows(store, business_id=business_id, view_id=view_id, limit=limit)


__all__ = [name for name in globals() if not name.startswith("__")]

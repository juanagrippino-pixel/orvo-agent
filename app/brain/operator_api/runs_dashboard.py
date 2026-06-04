from __future__ import annotations

from app.brain.run_ledger import TERMINAL_RUN_STATUSES, DispatchRunStatus, RunRecord

from .common import *  # noqa: F401,F403
from .common import _NO_DISPATCH_STATUS, RunDispatchStatusFilter
from .projections import *  # noqa: F401,F403
from .projections import _latest_dispatch_outcome
from .cases import *  # noqa: F401,F403
from .top_cases import *  # noqa: F401,F403
from .recent_cases import *  # noqa: F401,F403
from .workflow import *  # noqa: F401,F403
from .histograms_resolution import *  # noqa: F401,F403
from .histograms_ack import *  # noqa: F401,F403
from .histograms_handling import *  # noqa: F401,F403


def _latest_dispatch_status(run: RunRecord) -> DispatchRunStatus | None:
    latest = _latest_dispatch_outcome(run)
    return latest.status if latest is not None else None


def _matches_dispatch_status_filter(run: RunRecord, dispatch_status: RunDispatchStatusFilter) -> bool:
    latest_status = _latest_dispatch_status(run)
    if dispatch_status == _NO_DISPATCH_STATUS:
        return latest_status is None
    return latest_status == dispatch_status


def list_run_history(
    ledger: RunLedger,
    *,
    business_id: str,
    status: str | None,
    limit: str | None,
    trigger_type: str | None = None,
    dispatch_status: str | None = None,
) -> dict[str, Any]:
    parsed_status = parse_run_status(status)
    parsed_trigger_type = parse_run_trigger_type(trigger_type)
    parsed_dispatch_status = parse_dispatch_status(dispatch_status)
    parsed_limit = parse_limit(limit)
    runs = ledger.list_runs(
        business_id=business_id,
        status=parsed_status,
        trigger_type=parsed_trigger_type,
        limit=None if parsed_dispatch_status is not None else parsed_limit,
    )
    if parsed_dispatch_status is not None:
        runs = [run for run in runs if _matches_dispatch_status_filter(run, parsed_dispatch_status)]
        runs = runs[:parsed_limit]
    return {"runs": [run_history_item(run) for run in runs], "limit": parsed_limit}


def summarize_run_history(
    ledger: RunLedger,
    *,
    business_id: str,
    status: str | None,
    trigger_type: str | None,
    limit: str | None,
) -> dict[str, Any]:
    """Return bounded read-only analytics over business-scoped run ledger rows.

    This summary intentionally uses the ledger service API instead of SQL or user-
    supplied predicates. The route owns business scope, ``parse_limit`` caps the
    query window, and the response contains aggregate counts only.
    """

    parsed_status = parse_run_status(status)
    parsed_trigger_type = parse_run_trigger_type(trigger_type)
    parsed_limit = parse_limit(limit)
    runs = ledger.list_runs(
        business_id=business_id,
        status=parsed_status,
        trigger_type=parsed_trigger_type,
        limit=parsed_limit,
    )
    connector_outcomes = [outcome for run in runs for outcome in run.connector_outcomes]
    dispatch_outcomes = [outcome for run in runs for outcome in run.dispatch_outcomes]
    return redact_secrets(
        {
            "business_id": business_id,
            "filters": {"status": parsed_status, "trigger_type": parsed_trigger_type},
            "limit": parsed_limit,
            "count": len(runs),
            "status_counts": _sorted_counts(run.status for run in runs),
            "trigger_type_counts": _sorted_counts(run.trigger_type for run in runs),
            "connector_status_counts": _sorted_counts(outcome.status for outcome in connector_outcomes),
            "connector_type_counts": _sorted_counts(outcome.connector_type for outcome in connector_outcomes),
            "dispatch_status_counts": _sorted_counts(outcome.status for outcome in dispatch_outcomes),
            "terminal_total": sum(1 for run in runs if run.status in TERMINAL_RUN_STATUSES),
            "running_total": sum(1 for run in runs if run.status == "running"),
            "failed_connector_total": sum(1 for outcome in connector_outcomes if outcome.status == "failed"),
            "failed_dispatch_total": sum(1 for outcome in dispatch_outcomes if outcome.status == "failed"),
            "cases_opened_total": sum(_metadata_int(run.summary_metadata, "cases_opened") for run in runs),
            "cases_updated_total": sum(_metadata_int(run.summary_metadata, "cases_updated") for run in runs),
        }
    )


def _sorted_counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _metadata_int(metadata: dict[str, Any], key: str) -> int:
    value = metadata.get(key, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def get_scoped_run(ledger: RunLedger, *, business_id: str, run_id: str) -> RunRecord:
    run = ledger.get_run(run_id)
    if run is None or run.business_id != business_id:
        raise OperatorAPIError("run_not_found", "run not found", status_code=404)
    return run

def get_run_projection(ledger: RunLedger, *, business_id: str, run_id: str) -> dict[str, Any]:
    return {"run": run_detail(get_scoped_run(ledger, business_id=business_id, run_id=run_id))}

def get_operator_dashboard(
    store: OperationalCaseStore,
    ledger: RunLedger,
    *,
    business_id: str,
    now: datetime,
    limit: int = 10,
) -> dict[str, Any]:
    """Aggregate all key operator views for a business in one call.
    
    Returns a dashboard with:
    - case_queue_summary: counts by status, case_type, etc.
    - top_actionable_cases: highest priority cases needing attention
    - top_degraded_cases: cases with degraded freshness
    - workflow_throughput: acknowledgment/resolution rates
    - resolution_latency_histogram: time-to-resolve distribution
    - acknowledgment_latency_histogram: time-to-acknowledge distribution
    - run_history: recent run executions
    """
    return {
        "business_id": business_id,
        "now": _iso(now),
        "case_queue_summary": summarize_case_queue(store, business_id=business_id),
        "top_actionable_cases": list_top_actionable_cases_by_priority(
            store, business_id=business_id, now=now, limit=str(limit)
        ),
        "top_degraded_cases": list_top_actionable_degraded_cases(
            store, business_id=business_id, now=now, limit=str(limit)
        ),
        "workflow_throughput": summarize_case_workflow_throughput(
            store, business_id=business_id
        ),
        "resolution_latency_histogram": summarize_case_resolution_latency_histogram(
            store, business_id=business_id
        ),
        "acknowledgment_latency_histogram": summarize_case_acknowledgment_latency_histogram(
            store, business_id=business_id
        ),
        "run_history": list_run_history(
            ledger, business_id=business_id, status=None, trigger_type=None, limit=str(limit)
        ),
        "builtin_case_view_totals": _summarize_builtin_case_view_totals(
            store, business_id=business_id
        ),
    }


def _summarize_builtin_case_view_totals(store: OperationalCaseStore, *, business_id: str) -> dict[str, Any]:
    from app.brain.operator_views import summarize_builtin_case_view_totals

    return summarize_builtin_case_view_totals(store, business_id=business_id)

__all__ = [name for name in globals() if not name.startswith("__")]

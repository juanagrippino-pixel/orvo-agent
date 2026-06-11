from __future__ import annotations

from app.brain.run_ledger import DispatchRunStatus, RunRecord

from .common import *  # noqa: F401,F403
from .common import _NO_DISPATCH_STATUS, RunDispatchStatusFilter
from .projections import *  # noqa: F401,F403

_DISPATCH_STATUS_SUMMARY_KEYS: tuple[str, ...] = (
    "sent",
    "failed",
    "skipped_duplicate",
    "skipped",
    "queued",
)
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
    dispatch_status: str | None = None,
) -> dict[str, Any]:
    parsed_status = parse_run_status(status)
    parsed_dispatch_status = parse_dispatch_status(dispatch_status)
    parsed_limit = parse_limit(limit)
    runs = ledger.list_runs(
        business_id=business_id,
        status=parsed_status,
        limit=None if parsed_dispatch_status is not None else parsed_limit,
    )
    if parsed_dispatch_status is not None:
        runs = [run for run in runs if _matches_dispatch_status_filter(run, parsed_dispatch_status)]
        runs = runs[:parsed_limit]
    return {"runs": [run_history_item(run) for run in runs], "limit": parsed_limit}


def summarize_run_dispatch_statuses(
    ledger: RunLedger,
    *,
    business_id: str,
    status: str | None,
    limit: str | None,
) -> dict[str, Any]:
    parsed_status = parse_run_status(status)
    parsed_limit = parse_limit(limit)
    runs = ledger.list_runs(business_id=business_id, status=parsed_status, limit=parsed_limit)
    by_dispatch_status = {key: 0 for key in _DISPATCH_STATUS_SUMMARY_KEYS}
    by_dispatch_status[_NO_DISPATCH_STATUS] = 0
    for run in runs:
        latest_status = _latest_dispatch_status(run)
        if latest_status is None:
            by_dispatch_status[_NO_DISPATCH_STATUS] += 1
        else:
            by_dispatch_status[latest_status] += 1
    undispatched_runs = by_dispatch_status[_NO_DISPATCH_STATUS]
    total_runs = len(runs)
    return {
        "limit": parsed_limit,
        "run_status": parsed_status,
        "total_runs": total_runs,
        "dispatched_runs": total_runs - undispatched_runs,
        "undispatched_runs": undispatched_runs,
        "by_dispatch_status": by_dispatch_status,
    }


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
            ledger, business_id=business_id, status=None, limit=str(limit)
        ),
    }

__all__ = [name for name in globals() if not name.startswith("__")]

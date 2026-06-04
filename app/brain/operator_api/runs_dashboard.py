from __future__ import annotations

from .common import *  # noqa: F401,F403
from .projections import *  # noqa: F401,F403
from .cases import *  # noqa: F401,F403
from .top_cases import *  # noqa: F401,F403
from .recent_cases import *  # noqa: F401,F403
from .workflow import *  # noqa: F401,F403
from .histograms_resolution import *  # noqa: F401,F403
from .histograms_ack import *  # noqa: F401,F403
from .histograms_handling import *  # noqa: F401,F403


def list_run_history(ledger: RunLedger, *, business_id: str, status: str | None, limit: str | None) -> dict[str, Any]:
    parsed_status = parse_run_status(status)
    parsed_limit = parse_limit(limit)
    runs = ledger.list_runs(business_id=business_id, status=parsed_status, limit=parsed_limit)
    return {"runs": [run_history_item(run) for run in runs], "limit": parsed_limit}

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

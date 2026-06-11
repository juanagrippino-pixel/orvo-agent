from __future__ import annotations

from typing import Any

from app.brain.run_ledger import DispatchRunStatus, RunRecord

from .common import *  # noqa: F401,F403
from .common import _NO_DISPATCH_STATUS, RunDispatchMessageTypeFilter, RunDispatchStatusFilter
from .projections import *  # noqa: F401,F403

_DISPATCH_STATUS_SUMMARY_KEYS: tuple[str, ...] = (
    "sent",
    "failed",
    "skipped_duplicate",
    "skipped",
    "queued",
)
from .projections import _dispatch_message_type, _latest_dispatch_outcome, _redact_run_projection
from .cases import *  # noqa: F401,F403
from .top_cases import *  # noqa: F401,F403
from .recent_cases import *  # noqa: F401,F403
from .workflow import *  # noqa: F401,F403
from .histograms_resolution import *  # noqa: F401,F403
from .histograms_ack import *  # noqa: F401,F403
from .histograms_handling import *  # noqa: F401,F403


def _latest_dispatch_for_message_type(
    run: RunRecord,
    dispatch_message_type: RunDispatchMessageTypeFilter | None,
) -> Any | None:
    if dispatch_message_type is None:
        return _latest_dispatch_outcome(run)
    matching = [
        outcome for outcome in run.dispatch_outcomes if _dispatch_message_type(outcome) == dispatch_message_type
    ]
    if not matching:
        return None
    return max(matching, key=lambda outcome: (outcome.created_at, outcome.attempt_number))


def _latest_dispatch_status(
    run: RunRecord,
    dispatch_message_type: RunDispatchMessageTypeFilter | None = None,
) -> DispatchRunStatus | None:
    latest = _latest_dispatch_for_message_type(run, dispatch_message_type)
    return latest.status if latest is not None else None


def _matches_dispatch_message_type_filter(
    run: RunRecord,
    dispatch_message_type: RunDispatchMessageTypeFilter,
) -> bool:
    return _latest_dispatch_for_message_type(run, dispatch_message_type) is not None


def _matches_dispatch_status_filter(
    run: RunRecord,
    dispatch_status: RunDispatchStatusFilter,
    dispatch_message_type: RunDispatchMessageTypeFilter | None,
) -> bool:
    latest_status = _latest_dispatch_status(run, dispatch_message_type)
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
    dispatch_message_type: str | None = None,
) -> dict[str, Any]:
    parsed_status = parse_run_status(status)
    parsed_dispatch_status = parse_dispatch_status(dispatch_status)
    parsed_dispatch_message_type = parse_dispatch_message_type(dispatch_message_type)
    parsed_limit = parse_limit(limit)
    runs = ledger.list_runs(
        business_id=business_id,
        status=parsed_status,
        limit=None if parsed_dispatch_status is not None or parsed_dispatch_message_type is not None else parsed_limit,
    )
    if parsed_dispatch_message_type is not None:
        runs = [run for run in runs if _matches_dispatch_message_type_filter(run, parsed_dispatch_message_type)]
    if parsed_dispatch_status is not None:
        runs = [
            run
            for run in runs
            if _matches_dispatch_status_filter(run, parsed_dispatch_status, parsed_dispatch_message_type)
        ]
        runs = runs[:parsed_limit]
    elif parsed_dispatch_message_type is not None:
        runs = runs[:parsed_limit]
    payload: dict[str, Any] = {"runs": [run_history_item(run) for run in runs], "limit": parsed_limit}
    if parsed_dispatch_message_type is not None:
        payload["dispatch_message_type"] = parsed_dispatch_message_type
    return payload


def summarize_run_dispatch_statuses(
    ledger: RunLedger,
    *,
    business_id: str,
    status: str | None,
    limit: str | None,
    dispatch_message_type: str | None = None,
) -> dict[str, Any]:
    parsed_status = parse_run_status(status)
    parsed_dispatch_message_type = parse_dispatch_message_type(dispatch_message_type)
    parsed_limit = parse_limit(limit)
    runs = ledger.list_runs(
        business_id=business_id,
        status=parsed_status,
        limit=None if parsed_dispatch_message_type is not None else parsed_limit,
    )
    if parsed_dispatch_message_type is not None:
        runs = [run for run in runs if _matches_dispatch_message_type_filter(run, parsed_dispatch_message_type)]
        runs = runs[:parsed_limit]
    by_dispatch_status = {key: 0 for key in _DISPATCH_STATUS_SUMMARY_KEYS}
    by_dispatch_status[_NO_DISPATCH_STATUS] = 0
    for run in runs:
        latest_status = _latest_dispatch_status(run, parsed_dispatch_message_type)
        if latest_status is None:
            by_dispatch_status[_NO_DISPATCH_STATUS] += 1
        else:
            by_dispatch_status[latest_status] += 1
    undispatched_runs = by_dispatch_status[_NO_DISPATCH_STATUS]
    total_runs = len(runs)
    payload: dict[str, Any] = {
        "limit": parsed_limit,
        "run_status": parsed_status,
        "total_runs": total_runs,
        "dispatched_runs": total_runs - undispatched_runs,
        "undispatched_runs": undispatched_runs,
        "by_dispatch_status": by_dispatch_status,
    }
    if parsed_dispatch_message_type is not None:
        payload["dispatch_message_type"] = parsed_dispatch_message_type
    return payload


def get_scoped_run(ledger: RunLedger, *, business_id: str, run_id: str) -> RunRecord:
    run = ledger.get_run(run_id)
    if run is None or run.business_id != business_id:
        raise OperatorAPIError("run_not_found", "run not found", status_code=404)
    return run

def get_run_projection(ledger: RunLedger, *, business_id: str, run_id: str) -> dict[str, Any]:
    return {"run": run_detail(get_scoped_run(ledger, business_id=business_id, run_id=run_id))}


def _safe_run_dispatch_message_ids(run: RunRecord) -> list[str]:
    message_ids: list[str] = []
    for outcome in run.dispatch_outcomes:
        raw_message_id = outcome.message_id
        if not isinstance(raw_message_id, str):
            continue
        message_id = raw_message_id.strip()
        if not message_id:
            continue
        redacted = redact_text(message_id) or "[REDACTED]"
        if redacted != message_id:
            continue
        if message_id not in message_ids:
            message_ids.append(message_id)
    return message_ids


def get_run_delivery_status_projection(
    ledger: RunLedger,
    delivery_status_store: Any,
    *,
    business_id: str,
    run_id: str,
    limit: str | None = None,
) -> dict[str, Any]:
    run = get_scoped_run(ledger, business_id=business_id, run_id=run_id)
    parsed_limit = parse_limit(limit, max_limit=200)
    message_ids = _safe_run_dispatch_message_ids(run)
    events = delivery_status_store.list_by_message_ids(
        message_ids=message_ids,
        business_id=business_id,
        limit=parsed_limit,
    )
    return _redact_run_projection(
        {
            "run_id": run.run_id,
            "business_id": business_id,
            "dispatch_message_ids": message_ids,
            "limit": parsed_limit,
            "event_count": len(events),
            "events": events,
        }
    )


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

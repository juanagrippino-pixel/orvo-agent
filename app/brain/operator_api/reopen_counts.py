from __future__ import annotations

from typing import Any

from .common import (  # noqa: F401
    _ACTIONABLE_STATUSES,
    OperationalCaseStore,
    case_reopen_stats,
    redact_secrets,
)

_REOPEN_COUNT_BUCKETS: tuple[tuple[str, int | None], ...] = (
    ("none", 0),
    ("once", 1),
    ("twice", 2),
    ("three_to_five", 5),
    ("six_plus", None),
)


def _classify_reopen_count_bucket(reopen_count: int) -> str:
    for name, upper in _REOPEN_COUNT_BUCKETS:
        if upper is None or reopen_count <= upper:
            return name
    return _REOPEN_COUNT_BUCKETS[-1][0]


def _empty_reopen_buckets() -> dict[str, int]:
    return {name: 0 for name, _ in _REOPEN_COUNT_BUCKETS}


def summarize_case_reopen_counts(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Aggregate chronic-recurrence stats over the actionable queue.

    Counts only cases in actionable statuses, derives recurrence exclusively
    from canonical ``case_reopened`` timeline events, and scopes all reads to
    the requested business. Buckets are stable for operator surface widgets:
    ``none`` (0), ``once`` (1), ``twice`` (2), ``three_to_five`` (3-5), and
    ``six_plus`` (6+).
    """

    by_reopen_bucket = _empty_reopen_buckets()
    actionable_total = 0
    actionable_reopened_cases = 0
    actionable_total_reopens = 0
    actionable_max_reopen_count = 0
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        reopen_count, _latest_reopen_at = case_reopen_stats(case)
        actionable_total += 1
        actionable_total_reopens += reopen_count
        if reopen_count > 0:
            actionable_reopened_cases += 1
        actionable_max_reopen_count = max(actionable_max_reopen_count, reopen_count)
        by_reopen_bucket[_classify_reopen_count_bucket(reopen_count)] += 1
    return redact_secrets(
        {
            "business_id": business_id,
            "actionable_total": actionable_total,
            "actionable_reopened_cases": actionable_reopened_cases,
            "actionable_total_reopens": actionable_total_reopens,
            "actionable_max_reopen_count": actionable_max_reopen_count,
            "by_reopen_bucket": by_reopen_bucket,
        }
    )


def summarize_case_reopen_counts_by_severity(
    store: OperationalCaseStore, *, business_id: str
) -> dict[str, Any]:
    """Severity-split chronic-recurrence stats over actionable cases."""

    by_severity: dict[str, dict[str, Any]] = {}
    actionable_total = 0
    actionable_reopened_cases = 0
    actionable_total_reopens = 0
    actionable_max_reopen_count = 0
    for case in store.list_cases(business_id=business_id, limit=None):
        if case.status not in _ACTIONABLE_STATUSES:
            continue
        reopen_count, _latest_reopen_at = case_reopen_stats(case)
        bucket = _classify_reopen_count_bucket(reopen_count)
        actionable_total += 1
        actionable_total_reopens += reopen_count
        if reopen_count > 0:
            actionable_reopened_cases += 1
        actionable_max_reopen_count = max(actionable_max_reopen_count, reopen_count)

        severity_entry = by_severity.setdefault(
            case.severity,
            {
                "actionable_total": 0,
                "actionable_reopened_cases": 0,
                "actionable_total_reopens": 0,
                "actionable_max_reopen_count": 0,
                "by_reopen_bucket": _empty_reopen_buckets(),
            },
        )
        severity_entry["actionable_total"] += 1
        severity_entry["actionable_total_reopens"] += reopen_count
        if reopen_count > 0:
            severity_entry["actionable_reopened_cases"] += 1
        severity_entry["actionable_max_reopen_count"] = max(
            severity_entry["actionable_max_reopen_count"], reopen_count
        )
        severity_entry["by_reopen_bucket"][bucket] += 1
    return redact_secrets(
        {
            "business_id": business_id,
            "actionable_total": actionable_total,
            "actionable_reopened_cases": actionable_reopened_cases,
            "actionable_total_reopens": actionable_total_reopens,
            "actionable_max_reopen_count": actionable_max_reopen_count,
            "by_severity": by_severity,
        }
    )


__all__ = [name for name in globals() if not name.startswith("__")]

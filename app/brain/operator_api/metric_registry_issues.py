from __future__ import annotations

from .common import *  # noqa: F401,F403
from .common import _ACTIONABLE_STATUSES


def _metric_registry_issues_for_case(case: OperationalCase) -> list[dict[str, Any]]:
    """Return safe metric-registry advisory issues stored on a case."""

    raw_issues = case.metadata.get("metric_registry_issues")
    if not isinstance(raw_issues, list):
        return []
    issues: list[dict[str, Any]] = []
    for raw_issue in raw_issues:
        if not isinstance(raw_issue, dict):
            continue
        code = raw_issue.get("code")
        key = raw_issue.get("key")
        message = raw_issue.get("message")
        severity = raw_issue.get("severity")
        issues.append(
            {
                "code": redact_text(code) if isinstance(code, str) else "unknown_issue",
                "key": redact_text(key) if isinstance(key, str) else "unknown",
                "message": redact_text(message) if isinstance(message, str) else "Metric registry issue",
                "severity": redact_text(severity) if isinstance(severity, str) else "warning",
                "index": raw_issue.get("index") if isinstance(raw_issue.get("index"), int) else None,
            }
        )
    return issues


def summarize_case_metric_registry_issues(store: OperationalCaseStore, *, business_id: str) -> dict[str, Any]:
    """Summarize metric-registry advisory drift attached to canonical cases.

    The semantic metric registry remains the source of truth. This projection
    only reads advisory diagnostics already persisted on canonical
    ``OperationalCase.metadata`` so operator dashboards and CI checks can spot
    registry drift without scraping report text or re-running detections.
    """

    cases = store.list_cases(business_id=business_id, limit=None)
    by_code: dict[str, int] = {}
    by_metric_key: dict[str, int] = {}
    by_case_type: dict[str, int] = {}
    actionable_by_code: dict[str, int] = {}
    issue_cases: list[dict[str, Any]] = []
    issue_total = 0
    actionable_issue_total = 0
    actionable_case_total = 0

    for case in cases:
        issues = _metric_registry_issues_for_case(case)
        if not issues:
            continue
        actionable = case.status in _ACTIONABLE_STATUSES
        if actionable:
            actionable_case_total += 1
        by_case_type[case.case_type] = by_case_type.get(case.case_type, 0) + 1
        issue_total += len(issues)
        if actionable:
            actionable_issue_total += len(issues)
        for issue in issues:
            code = issue["code"]
            key = issue["key"]
            by_code[code] = by_code.get(code, 0) + 1
            by_metric_key[key] = by_metric_key.get(key, 0) + 1
            if actionable:
                actionable_by_code[code] = actionable_by_code.get(code, 0) + 1
        issue_cases.append(
            {
                "case_id": case.case_id,
                "case_type": case.case_type,
                "status": case.status,
                "severity": case.severity,
                "priority_score": case.priority_score,
                "latest_run_id": case.latest_run_id,
                "issue_count": len(issues),
                "issues": issues,
            }
        )

    actionable_statuses = set(_ACTIONABLE_STATUSES)
    issue_cases.sort(
        key=lambda item: (
            0 if item["status"] in actionable_statuses else 1,
            -int(item["priority_score"]),
            str(item["case_id"]),
        )
    )
    metric_key_counts = [
        {"metric_key": key, "count": by_metric_key[key]} for key in sorted(by_metric_key)
    ]
    return redact_secrets(
        {
            "business_id": business_id,
            "total_cases": len(cases),
            "cases_with_metric_registry_issues": len(issue_cases),
            "actionable_cases_with_metric_registry_issues": actionable_case_total,
            "issue_total": issue_total,
            "actionable_issue_total": actionable_issue_total,
            "by_code": by_code,
            "actionable_by_code": actionable_by_code,
            "by_metric_key": metric_key_counts,
            "by_case_type": by_case_type,
            "issue_cases": issue_cases,
        }
    )


__all__ = [name for name in globals() if not name.startswith("__")]

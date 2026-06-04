"""Central merge policy for multi-connector DailyReport payloads.

The policy is intentionally explicit because adapter workers can emit the same
canonical metric family from different sources. Downstream insight generation and
operator surfaces must see one deterministic metric per key.
"""

from __future__ import annotations

from typing import cast

from app.brain.config import BusinessConfig
from app.brain.insights import generate_insights
from app.brain.models import DailyReport, Evidence, Metric

MERGE_POLICY_VERSION = "daily-report-merge-v1"


def _is_number(value: float | int | str) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _merge_evidence(left: list[Evidence], right: list[Evidence]) -> list[Evidence]:
    evidence = list(left)
    seen = {(item.source, item.label) for item in evidence}
    for item in right:
        key = (item.source, item.label)
        if key not in seen:
            evidence.append(item)
            seen.add(key)
    return evidence


def merge_duplicate_metric(existing: Metric, incoming: Metric) -> Metric:
    """Merge two metrics with the same canonical key.

    Numeric duplicates with the same unit are additive and preserve unique
    evidence in first-seen order. Non-numeric duplicates or unit mismatches are
    resolved by deterministic last-wins replacement, matching legacy pipeline
    behavior before this policy was centralized.
    """

    if _is_number(existing.value) and _is_number(incoming.value) and existing.unit == incoming.unit:
        existing_value = cast(float | int, existing.value)
        incoming_value = cast(float | int, incoming.value)
        return existing.model_copy(
            update={
                "value": existing_value + incoming_value,
                "evidence": _merge_evidence(existing.evidence, incoming.evidence),
            }
        )
    return incoming


def merge_daily_reports(reports: list[DailyReport], *, business: BusinessConfig | None = None) -> DailyReport:
    """Merge adapter reports into one DailyReport using ``MERGE_POLICY_VERSION``.

    Duplicate metric keys are collapsed so downstream insight/report code sees a
    single canonical key. Numeric duplicates with the same unit are summed and
    their evidence is combined; non-numeric or unit-mismatched duplicates use
    last-wins to keep the key unique and deterministic.
    """

    if not reports:
        raise ValueError("at least one report is required to merge daily reports")
    if len(reports) == 1 and business is None:
        return reports[0]

    merged_by_key: dict[str, Metric] = {}
    for report in reports:
        for metric in report.metrics:
            existing = merged_by_key.get(metric.key)
            if existing is None:
                merged_by_key[metric.key] = metric
                continue
            merged_by_key[metric.key] = merge_duplicate_metric(existing, metric)

    metrics = list(merged_by_key.values())
    return DailyReport(
        business_name=reports[0].business_name,
        report_date=reports[0].report_date,
        metrics=metrics,
        insights=generate_insights(metrics, thresholds=business.insight_thresholds if business else None),
    )

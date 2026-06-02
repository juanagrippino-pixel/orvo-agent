"""CSV adapter for Orvo Brain concierge ingestion."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from app.brain.adapters.google_sheets import build_metrics_from_sheet_records, normalize_header
from app.brain.insights import generate_insights
from app.brain.models import DailyReport, Evidence, InsightThresholds, Metric


def _read_csv_records(csv_path: str) -> list[dict[str, str]]:
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        records: list[dict[str, str]] = []
        for row in reader:
            normalized = {
                normalize_header(key): str(value).strip()
                for key, value in row.items()
                if key is not None and value is not None and str(value).strip() != ""
            }
            if any(normalized.values()):
                records.append(normalized)
        return records


def _with_csv_evidence(metrics: list[Metric], *, csv_path: str, source_label: str) -> list[Metric]:
    evidence = [Evidence(source="csv", label=f"{source_label} · {Path(csv_path).resolve()}")]
    return [metric.model_copy(update={"evidence": evidence}) for metric in metrics]


def build_daily_report_from_csv_file(
    *,
    business_name: str,
    report_date: date,
    csv_path: str,
    source_label: str | None = None,
    insight_thresholds: InsightThresholds | None = None,
) -> DailyReport:
    """Build a cited daily report from a local CSV export."""

    records = _read_csv_records(csv_path)
    label = source_label or f"CSV {Path(csv_path).name}"
    metrics = build_metrics_from_sheet_records(
        records,
        business_name=business_name,
        report_date=report_date,
        source_label=label,
        spreadsheet_id=Path(csv_path).name,
        range_name="csv",
    )
    metrics = _with_csv_evidence(metrics, csv_path=csv_path, source_label=label)
    return DailyReport(
        business_name=business_name,
        report_date=report_date,
        metrics=metrics,
        insights=generate_insights(metrics, thresholds=insight_thresholds),
    )

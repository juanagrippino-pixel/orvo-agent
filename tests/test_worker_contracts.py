from __future__ import annotations

from datetime import date

import pytest

from app.brain.models import DailyReport, Evidence, Metric


def _report(metrics: list[Metric]) -> DailyReport:
    return DailyReport(business_name="Artemea", report_date=date(2026, 5, 26), metrics=metrics, insights=[])


def _metric(key: str, value, *, unit: str | None = None, source: str = "csv") -> Metric:
    return Metric(
        key=key,
        label=key.replace("_", " ").title(),
        value=value,
        unit=unit,
        evidence=[Evidence(source=source, label=source.upper())],
    )


def test_merge_daily_reports_lives_in_central_policy_and_keeps_pipeline_compatibility():
    from app.brain.pipeline import merge_daily_reports as pipeline_merge_daily_reports
    from app.brain.report_merge_policy import MERGE_POLICY_VERSION, merge_daily_reports

    assert pipeline_merge_daily_reports is merge_daily_reports
    assert MERGE_POLICY_VERSION == "daily-report-merge-v1"

    merged = merge_daily_reports(
        [
            _report([_metric("revenue_today", 100, unit="ARS", source="tiendanube")]),
            _report([_metric("revenue_today", 50, unit="ARS", source="meta_ads")]),
            _report([_metric("stock_state", "low", source="csv")]),
            _report([_metric("stock_state", "ok", source="sheets")]),
        ]
    )

    by_key = {metric.key: metric for metric in merged.metrics}
    assert by_key["revenue_today"].value == 150
    assert [e.source for e in by_key["revenue_today"].evidence] == ["tiendanube", "meta_ads"]
    assert by_key["stock_state"].value == "ok"


def test_adapter_worker_protocol_names_required_stages_and_validates_factories():
    from app.brain.worker_contracts import (
        ADAPTER_WORKER_STAGES,
        AdapterWorkerContext,
        validate_daily_report_adapter,
    )

    assert ADAPTER_WORKER_STAGES == (
        "validate",
        "fetch",
        "build_report",
        "emit_metrics",
        "record_freshness",
    )

    context = AdapterWorkerContext(
        business_id="artemea",
        connector_id="csv-main",
        connector_type="csv",
        report_date=date(2026, 5, 26),
        run_id="run_123",
    )
    assert context.correlation_id == "run_123:csv-main"

    def factory(**kwargs):
        return _report([_metric("orders_today", 3)])

    assert validate_daily_report_adapter(factory) is factory
    with pytest.raises(TypeError, match="callable"):
        validate_daily_report_adapter(object())

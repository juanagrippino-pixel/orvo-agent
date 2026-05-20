"""End-to-end Orvo Brain report pipelines."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.brain.adapters.csv_file import build_daily_report_from_csv_file
from app.brain.adapters.google_sheets import build_daily_report_from_sheet
from app.brain.adapters.mercadolibre import build_daily_report_from_mercadolibre
from app.brain.adapters.meta_ads import build_daily_report_from_meta_ads
from app.brain.adapters.tiendanube import build_daily_report_from_tiendanube
from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.delivery import WhatsAppDeliveryClient
from app.brain.dispatch import IdempotencyStore, ReportDispatchResult, dispatch_daily_report
from app.brain.models import DailyReport, Metric


class PipelineResult(BaseModel):
    report: DailyReport
    dispatch: ReportDispatchResult


def _find_google_sheets_connector(business: BusinessConfig) -> ConnectorConfig:
    for connector in business.connectors:
        if connector.enabled and connector.connector_type == "google_sheets":
            return connector
    raise ValueError(f"Business {business.business_id} has no enabled google_sheets connector")


def _find_tiendanube_connector(business: BusinessConfig) -> ConnectorConfig:
    for connector in business.connectors:
        if connector.enabled and connector.connector_type == "tiendanube":
            return connector
    raise ValueError(f"Business {business.business_id} has no enabled tiendanube connector")


def _find_csv_connector(business: BusinessConfig) -> ConnectorConfig:
    for connector in business.connectors:
        if connector.enabled and connector.connector_type == "csv":
            return connector
    raise ValueError(f"Business {business.business_id} has no enabled csv connector")


def _find_meta_ads_connector(business: BusinessConfig) -> ConnectorConfig:
    for connector in business.connectors:
        if connector.enabled and connector.connector_type == "meta_ads":
            return connector
    raise ValueError(f"Business {business.business_id} has no enabled meta_ads connector")


def _find_mercadolibre_connector(business: BusinessConfig) -> ConnectorConfig:
    for connector in business.connectors:
        if connector.enabled and connector.connector_type == "mercadolibre":
            return connector
    raise ValueError(f"Business {business.business_id} has no enabled mercadolibre connector")


def merge_daily_reports(reports: list[DailyReport]) -> DailyReport:
    """Merge metrics from multiple DailyReport objects into one.

    Merging strategy:
    - If a metric key appears in only one report it is kept as-is.
    - If the same key appears across multiple reports, each is namespaced as
      ``<connector_label>.<key>`` derived from the evidence source label on
      the metric (first evidence entry).  This makes duplicates distinct while
      preserving the original key for single-source metrics.
    - Insights are concatenated in order (first report's insights first).
    - business_name and report_date are taken from the first report.

    Callers must pass at least one report.
    """
    if not reports:
        raise ValueError("merge_daily_reports requires at least one report")
    if len(reports) == 1:
        return reports[0]

    # Count how many reports contribute each key
    from collections import Counter

    key_count: Counter[str] = Counter()
    for report in reports:
        for metric in report.metrics:
            key_count[metric.key] += 1

    merged_metrics: list[Metric] = []
    for report in reports:
        for metric in report.metrics:
            if key_count[metric.key] > 1:
                # Namespace by the evidence source label (e.g. "tiendanube" -> "tiendanube.revenue_today")
                source_label = metric.evidence[0].source if metric.evidence else "unknown"
                namespaced_key = f"{source_label}.{metric.key}"
                namespaced_label = f"[{source_label}] {metric.label}"
                merged_metrics.append(
                    Metric(
                        key=namespaced_key,
                        label=namespaced_label,
                        value=metric.value,
                        unit=metric.unit,
                        evidence=metric.evidence,
                    )
                )
            else:
                merged_metrics.append(metric)

    merged_insights = []
    for report in reports:
        merged_insights.extend(report.insights)

    return DailyReport(
        business_name=reports[0].business_name,
        report_date=reports[0].report_date,
        metrics=merged_metrics,
        insights=merged_insights,
    )


def run_google_sheets_daily_report_pipeline(
    *,
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
    sheets_service=None,
) -> PipelineResult:
    """Build a daily report from Google Sheets and dispatch it to WhatsApp."""

    connector = _find_google_sheets_connector(business)
    spreadsheet_id = connector.params.get("spreadsheet_id")
    range_name = connector.params.get("range_name")
    if not spreadsheet_id or not range_name:
        raise ValueError("google_sheets connector params must include spreadsheet_id and range_name")

    report = build_daily_report_from_sheet(
        business_name=business.business_name,
        report_date=report_date,
        spreadsheet_id=spreadsheet_id,
        range_name=range_name,
        source_label=connector.label,
        service=sheets_service,
        insight_thresholds=business.insight_thresholds,
    )
    dispatch = dispatch_daily_report(
        report=report,
        business=business,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
    )
    return PipelineResult(report=report, dispatch=dispatch)


def run_tiendanube_daily_report_pipeline(
    *,
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
    http_client=None,
) -> PipelineResult:
    """Build a daily report from Tiendanube and dispatch it to WhatsApp."""

    connector = _find_tiendanube_connector(business)
    store_id = connector.params.get("store_id")
    access_token = connector.params.get("access_token")
    if not store_id or not access_token:
        raise ValueError("tiendanube connector params must include store_id and access_token")

    report = build_daily_report_from_tiendanube(
        business_name=business.business_name,
        report_date=report_date,
        store_id=store_id,
        access_token=access_token,
        include_stock=bool(connector.params.get("include_stock", False)),
        source_label=connector.label,
        http_client=http_client,
    )
    dispatch = dispatch_daily_report(
        report=report,
        business=business,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
    )
    return PipelineResult(report=report, dispatch=dispatch)


def run_csv_daily_report_pipeline(
    *,
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
) -> PipelineResult:
    """Build a daily report from a local CSV file and dispatch it to WhatsApp."""

    connector = _find_csv_connector(business)
    csv_path = connector.params.get("csv_path")
    if not csv_path:
        raise ValueError("csv connector params must include csv_path")

    report = build_daily_report_from_csv_file(
        business_name=business.business_name,
        report_date=report_date,
        csv_path=csv_path,
        source_label=connector.params.get("source_label") or connector.label,
        insight_thresholds=business.insight_thresholds,
    )
    dispatch = dispatch_daily_report(
        report=report,
        business=business,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
    )
    return PipelineResult(report=report, dispatch=dispatch)


def run_mercadolibre_daily_report_pipeline(
    *,
    business: BusinessConfig,
    report_date: date,
    delivery_client: WhatsAppDeliveryClient,
    idempotency_store: IdempotencyStore,
    http_client=None,
) -> PipelineResult:
    """Build a daily report from MercadoLibre and dispatch it to WhatsApp."""

    connector = _find_mercadolibre_connector(business)
    seller_id = connector.params.get("seller_id")
    access_token = connector.params.get("access_token")
    if not seller_id or not access_token:
        raise ValueError("mercadolibre connector params must include seller_id and access_token")

    report = build_daily_report_from_mercadolibre(
        business_name=business.business_name,
        report_date=report_date,
        seller_id=seller_id,
        access_token=access_token,
        site_id=connector.params.get("site_id", "MLA"),
        source_label=connector.params.get("source_label") or connector.label,
        http_client=http_client,
    )
    dispatch = dispatch_daily_report(
        report=report,
        business=business,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
    )
    return PipelineResult(report=report, dispatch=dispatch)

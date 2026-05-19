"""End-to-end Orvo Brain report pipelines."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.brain.adapters.csv_file import build_daily_report_from_csv_file
from app.brain.adapters.google_sheets import build_daily_report_from_sheet
from app.brain.adapters.tiendanube import build_daily_report_from_tiendanube
from app.brain.config import BusinessConfig, ConnectorConfig
from app.brain.delivery import WhatsAppDeliveryClient
from app.brain.dispatch import IdempotencyStore, ReportDispatchResult, dispatch_daily_report
from app.brain.models import DailyReport


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
    )
    dispatch = dispatch_daily_report(
        report=report,
        business=business,
        delivery_client=delivery_client,
        idempotency_store=idempotency_store,
    )
    return PipelineResult(report=report, dispatch=dispatch)

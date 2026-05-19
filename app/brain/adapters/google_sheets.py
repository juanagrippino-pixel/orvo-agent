"""Google Sheets adapter for Orvo Brain concierge ingestion."""

from __future__ import annotations

import os
import re
import unicodedata
from datetime import date, timedelta
from typing import Any

from app.brain.adapters.sample import METRIC_LABELS
from app.brain.insights import generate_insights
from app.brain.models import DailyReport, Evidence, Metric

HEADER_ALIASES = {
    "fecha": "date",
    "date": "date",
    "ventas": "revenue",
    "venta": "revenue",
    "revenue": "revenue",
    "facturacion": "revenue",
    "facturación": "revenue",
    "ordenes": "orders",
    "órdenes": "orders",
    "orders": "orders",
    "pedidos": "orders",
    "stock": "stock_units",
    "stock_units": "stock_units",
    "unidades_stock": "stock_units",
    "conversaciones_sin_responder": "unanswered_conversations",
    "sin_responder": "unanswered_conversations",
    "mensajes_pendientes": "unanswered_conversations",
    "gasto_ads": "ad_spend",
    "ads": "ad_spend",
    "ad_spend": "ad_spend",
    "meta_ads": "ad_spend",
}

METRIC_ORDER = [
    "revenue_today",
    "revenue_baseline",
    "orders_today",
    "stock_units",
    "unanswered_conversations",
    "ad_spend_today",
]


def normalize_header(header: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(header).strip().lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return HEADER_ALIASES.get(normalized, normalized)


def parse_number(value: str | int | float | None) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    cleaned = str(value).strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace("$", "").replace("ARS", "").replace(" ", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", cleaned):
        cleaned = cleaned.replace(".", "")
    try:
        parsed = float(cleaned)
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def rows_to_records(values: list[list[str]]) -> list[dict[str, str]]:
    if not values:
        raise ValueError("Google Sheet is empty")
    headers = [normalize_header(cell) for cell in values[0]]
    if "date" not in headers:
        raise ValueError("Google Sheet must include a fecha/date column")

    records: list[dict[str, str]] = []
    for row in values[1:]:
        if not any(str(cell).strip() for cell in row):
            continue
        record: dict[str, str] = {}
        for idx, header in enumerate(headers):
            if idx < len(row) and str(row[idx]).strip() != "":
                record[header] = str(row[idx]).strip()
        records.append(record)
    return records


def get_sheets_service(*, credentials_file: str | None = None, scopes: list[str] | None = None):
    credentials_path = credentials_file or os.environ.get("GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE")
    if not credentials_path:
        raise ValueError("GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE is required")
    scopes = scopes or [os.environ.get("GOOGLE_SHEETS_SCOPES", "https://www.googleapis.com/auth/spreadsheets.readonly")]

    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    return build("sheets", "v4", credentials=credentials)


def fetch_sheet_values(spreadsheet_id: str, range_name: str, *, service=None) -> list[list[str]]:
    service = service or get_sheets_service()
    result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    return result.get("values", [])


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _evidence(source_label: str, spreadsheet_id: str, range_name: str) -> list[Evidence]:
    return [
        Evidence(
            source="google_sheets",
            label=f"{source_label} · {range_name}",
            url=f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
        )
    ]


def _make_metric(key: str, value: float | int, evidence: list[Evidence]) -> Metric:
    label, unit = METRIC_LABELS.get(key, (key.replace("_", " ").title(), None))
    return Metric(key=key, label=label, value=value, unit=unit, evidence=evidence)


def build_metrics_from_sheet_records(
    records: list[dict[str, str]],
    *,
    business_name: str,
    report_date: date,
    source_label: str,
    spreadsheet_id: str,
    range_name: str,
) -> list[Metric]:
    del business_name  # Reserved for future business-specific normalization.
    source = _evidence(source_label, spreadsheet_id, range_name)
    today_rows = [record for record in records if _parse_date(record.get("date")) == report_date]
    if not today_rows:
        raise ValueError(f"No rows found for report_date {report_date.isoformat()}")

    values: dict[str, float | int] = {}

    revenue_today = sum(parse_number(record.get("revenue")) or 0 for record in today_rows)
    if revenue_today:
        values["revenue_today"] = revenue_today

    previous_revenues: list[float | int] = []
    min_date = report_date - timedelta(days=7)
    for record in records:
        record_date = _parse_date(record.get("date"))
        revenue = parse_number(record.get("revenue"))
        if record_date and min_date <= record_date < report_date and revenue is not None:
            previous_revenues.append(revenue)
    if previous_revenues:
        values["revenue_baseline"] = round(sum(previous_revenues) / len(previous_revenues), 2)

    orders = [parse_number(record.get("orders")) for record in today_rows]
    orders = [value for value in orders if value is not None]
    if orders:
        values["orders_today"] = sum(orders)

    stock_values = [parse_number(record.get("stock_units")) for record in today_rows]
    stock_values = [value for value in stock_values if value is not None]
    if stock_values:
        values["stock_units"] = min(stock_values)

    unanswered = [parse_number(record.get("unanswered_conversations")) for record in today_rows]
    unanswered = [value for value in unanswered if value is not None]
    if unanswered:
        values["unanswered_conversations"] = max(unanswered)

    ad_spend = [parse_number(record.get("ad_spend")) for record in today_rows]
    ad_spend = [value for value in ad_spend if value is not None]
    if ad_spend:
        values["ad_spend_today"] = sum(ad_spend)

    return [_make_metric(key, values[key], source) for key in METRIC_ORDER if key in values]


def build_daily_report_from_sheet(
    *,
    business_name: str,
    report_date: date,
    spreadsheet_id: str,
    range_name: str,
    source_label: str | None = None,
    service=None,
) -> DailyReport:
    values = fetch_sheet_values(spreadsheet_id, range_name, service=service)
    records = rows_to_records(values)
    metrics = build_metrics_from_sheet_records(
        records,
        business_name=business_name,
        report_date=report_date,
        source_label=source_label or f"Google Sheet {business_name}",
        spreadsheet_id=spreadsheet_id,
        range_name=range_name,
    )
    return DailyReport(
        business_name=business_name,
        report_date=report_date,
        metrics=metrics,
        insights=generate_insights(metrics),
    )

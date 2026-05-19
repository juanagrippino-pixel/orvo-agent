"""Sample/manual adapter for concierge Orvo Brain onboarding."""

from datetime import date
from typing import Any

from app.brain.insights import generate_insights
from app.brain.models import DailyReport, Evidence, Metric

METRIC_LABELS = {
    "revenue_today": ("Ventas de hoy", "ARS"),
    "revenue_baseline": ("Promedio reciente", "ARS"),
    "stock_units": ("Stock disponible", "units"),
    "unanswered_conversations": ("Conversaciones sin responder", None),
    "orders_today": ("Órdenes", None),
    "ad_spend_today": ("Gasto en anuncios", "ARS"),
}


def _parse_date(raw: Any) -> date:
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw:
        return date.fromisoformat(raw)
    return date.today()


def build_metrics_from_payload(payload: dict[str, Any]) -> list[Metric]:
    """Normalize a simple JSON-like payload into cited metrics."""

    source = Evidence(
        source=str(payload.get("source") or "manual_sample"),
        label=str(payload.get("source_label") or "Carga manual Orvo Brain"),
    )
    metrics_payload = payload.get("metrics") or {}
    metrics: list[Metric] = []
    for key, value in metrics_payload.items():
        label, unit = METRIC_LABELS.get(key, (key.replace("_", " ").title(), None))
        metrics.append(
            Metric(
                key=key,
                label=label,
                value=value,
                unit=unit,
                evidence=[source],
            )
        )
    return metrics


def build_daily_report_from_payload(payload: dict[str, Any]) -> DailyReport:
    """Build a complete daily report from manually supplied business data."""

    metrics = build_metrics_from_payload(payload)
    return DailyReport(
        business_name=str(payload.get("business_name") or "Negocio"),
        report_date=_parse_date(payload.get("report_date")),
        metrics=metrics,
        insights=generate_insights(metrics),
    )

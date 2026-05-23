"""Report composition for WhatsApp-first Orvo Brain output."""

from app.brain.models import DailyReport, Evidence, Metric


def _format_value(metric: Metric) -> str:
    value = metric.value
    if isinstance(value, (int, float)):
        if metric.unit == "ARS":
            return f"ARS {value:,.0f}".replace(",", ".")
        if metric.unit:
            return f"{value:g} {metric.unit}"
        return f"{value:g}"
    return str(value)


def _metrics_by_key(report: DailyReport) -> dict:
    return {m.key: m for m in report.metrics}


def _format_ars(value: float) -> str:
    return f"ARS {value:,.0f}".replace(",", ".")


_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

_TN_REVENUE_KEYS = (
    "revenue_today_tn",
    "tiendanube.revenue_today",
    "tn_revenue_today",
)
_ML_REVENUE_KEYS = (
    "revenue_today_ml",
    "mercadolibre.revenue_today",
    "ml_revenue_today",
)


def _first_metric(metrics: dict, keys: tuple[str, ...]) -> Metric | None:
    for key in keys:
        metric = metrics.get(key)
        if metric is not None:
            return metric
    return None


def _metric_float(metrics: dict, keys: tuple[str, ...]) -> float | None:
    metric = _first_metric(metrics, keys)
    if metric is None:
        return None
    return float(metric.value)


def _canales_section(metrics: dict) -> list[str]:
    tn_val = _metric_float(metrics, _TN_REVENUE_KEYS)
    ml_val = _metric_float(metrics, _ML_REVENUE_KEYS)
    if tn_val is None or ml_val is None:
        return []
    total = tn_val + ml_val
    return [
        "",
        "📦 Canales",
        f"- Tiendanube: {_format_ars(tn_val)}",
        f"- MercadoLibre: {_format_ars(ml_val)}",
        f"- Total: {_format_ars(total)}",
    ]


def _ads_section(metrics: dict) -> list[str]:
    ad = metrics.get("ad_spend_today")
    if not ad:
        return []
    spend = float(ad.value)
    revenue = sum(
        value
        for value in (
            _metric_float(metrics, _TN_REVENUE_KEYS),
            _metric_float(metrics, _ML_REVENUE_KEYS),
        )
        if value is not None
    )
    roas_line = f"- ROAS estimado: {revenue / spend:.1f}x" if spend > 0 else "- ROAS estimado: N/A"
    return [
        "",
        "📣 Publicidad",
        f"- Gasto del día: {_format_ars(spend)}",
        roas_line,
    ]


def _compact_sources(report: DailyReport) -> str:
    seen: set[str] = set()
    labels: list[str] = []
    for metric in report.metrics:
        for evidence in metric.evidence:
            if evidence.source not in seen:
                labels.append(evidence.label)
                seen.add(evidence.source)
    for insight in report.insights:
        for evidence in insight.evidence:
            if evidence.source not in seen:
                labels.append(evidence.label)
                seen.add(evidence.source)
    if not labels:
        return "🔗 Fuentes: Sin fuentes"
    return "🔗 Fuentes: " + " · ".join(labels)


def compose_daily_report_text(report: DailyReport) -> str:
    """Compose a short, cited Spanish daily report for a business owner."""

    mkeys = _metrics_by_key(report)

    lines = [
        f"🧠 Orvo Brain — {report.business_name}",
        f"Reporte diario · {report.report_date.isoformat()}",
        "",
        "📊 Métricas",
    ]

    if report.metrics:
        for metric in report.metrics:
            lines.append(f"- {metric.label}: {_format_value(metric)}")
    else:
        lines.append("- Sin métricas cargadas todavía")

    # Cross-channel section (only when both TN + ML present)
    lines.extend(_canales_section(mkeys))

    # Ads section (only when ad_spend_today present)
    lines.extend(_ads_section(mkeys))

    lines.extend(["", "🚨 Alertas"])
    if report.insights:
        for insight in sorted(report.insights, key=lambda i: _SEVERITY_ORDER.get(i.severity, 9)):
            if insight.severity == "critical":
                prefix = "🔴"
                urgency = "Acción urgente:"
            elif insight.severity == "warning":
                prefix = "🟡"
                urgency = "Acción:"
            else:
                prefix = "ℹ️"
                urgency = "Acción:"
            lines.append(f"{prefix} {insight.title}: {insight.explanation}")
            lines.append(f"   {urgency} {insight.recommended_action}")
    else:
        lines.append("✅ Sin alertas críticas por ahora.")

    # Compact footer
    lines.extend(["", _compact_sources(report)])

    return "\n".join(lines)


def truncate_for_whatsapp(text: str, max_chars: int = 1000) -> str:
    """Trim a report to fit WhatsApp's practical reading budget.

    Keeps the text unchanged if under max_chars. Otherwise trims and appends
    '... (ver reporte completo)'.
    """
    if len(text) <= max_chars:
        return text
    suffix = "... (ver reporte completo)"
    return text[: max_chars - len(suffix)] + suffix

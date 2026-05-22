"""Report composition for WhatsApp-first Orvo Brain output."""

from app.brain.models import DailyReport, Metric


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
_REVENUE_KEYS = ("revenue_today", *_TN_REVENUE_KEYS)
_ORDERS_KEYS = ("orders_today", "orders_today_tn", "tiendanube.orders_today")
_STOCK_KEYS = ("stock_units",)
_UNANSWERED_KEYS = ("unanswered_conversations",)


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
        "Canales:",
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
    if revenue == 0:
        revenue = _metric_float(metrics, ("revenue_today",)) or 0
    roas_line = f"- ROAS estimado: {revenue / spend:.1f}x" if spend > 0 and revenue > 0 else "- ROAS estimado: N/A"
    return [
        "",
        "Publicidad:",
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
        return "Fuentes: sin fuentes"
    return "Fuentes: " + " · ".join(labels)


def _clean_sentence(text: str) -> str:
    stripped = " ".join(text.strip().split())
    if not stripped:
        return stripped
    return stripped if stripped.endswith((".", "?", "!")) else stripped + "."


def _priority_line(report: DailyReport) -> str:
    if not report.metrics:
        return "Prioridad: no enviar conclusiones hasta cargar datos."
    if not report.insights:
        return "Prioridad: no hay urgencia hoy."
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    primary = sorted(report.insights, key=lambda item: severity_rank[item.severity])[0]
    return "Prioridad: " + _clean_sentence(primary.recommended_action)


def _finding_lines(report: DailyReport) -> list[str]:
    if not report.metrics:
        return ["Datos insuficientes para leer ventas, ads o stock."]
    if report.insights:
        severity_rank = {"critical": 0, "warning": 1, "info": 2}
        primary = sorted(report.insights, key=lambda item: severity_rank[item.severity])[0]
        return [_clean_sentence(primary.explanation)]
    return ["No hay alertas críticas con los datos disponibles."]


def _main_fact_lines(metrics: dict) -> list[str]:
    selected: list[Metric] = []
    for keys in (_REVENUE_KEYS, _ORDERS_KEYS, ("ad_spend_today",), _STOCK_KEYS, _UNANSWERED_KEYS):
        metric = _first_metric(metrics, keys)
        if metric is not None and metric not in selected:
            selected.append(metric)
        if len(selected) >= 3:
            break
    return [f"- {metric.label}: {_format_value(metric)}" for metric in selected]


def _secondary_line(report: DailyReport) -> str | None:
    if len(report.insights) < 2:
        return None
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    secondary = sorted(report.insights, key=lambda item: severity_rank[item.severity])[1]
    return "Secundario: " + _clean_sentence(secondary.title)


def compose_daily_report_text(report: DailyReport) -> str:
    """Compose a terse, operator-style Spanish WhatsApp report.

    Hito 0 target: Juan should see the first action, the facts behind it, and
    data sources without AI-sounding framing, hype, emojis, or dashboard dump.
    """

    mkeys = _metrics_by_key(report)
    header_name = report.business_name
    state = " · parcial" if not report.metrics else ""
    lines = [
        f"{header_name} · {report.report_date.isoformat()}{state}",
        _priority_line(report),
        "",
        *_finding_lines(report),
    ]

    facts = _main_fact_lines(mkeys)
    if facts:
        lines.extend(["", *facts])

    lines.extend(_canales_section(mkeys))
    lines.extend(_ads_section(mkeys))

    secondary = _secondary_line(report)
    if secondary:
        lines.extend(["", secondary])

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

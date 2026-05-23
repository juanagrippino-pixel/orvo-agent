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
_TOTAL_REVENUE_KEYS = (
    "revenue_today",
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
    total_revenue = _metric_float(metrics, _TOTAL_REVENUE_KEYS)
    revenue = total_revenue if total_revenue is not None else sum(
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
        return "Fuentes: sin fuentes"
    return "Fuentes: " + ", ".join(labels)


def _business_label(name: str) -> str:
    """Return the terse owner-facing business label for the report header."""

    stripped = name.strip()
    if stripped.casefold() == "artemea":
        return "ARTEMEA"
    return stripped


def _ensure_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    if stripped[-1] in ".!?":
        return stripped
    return stripped + "."


def _primary_insight(report: DailyReport) -> object | None:
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    if not report.insights:
        return None
    return sorted(report.insights, key=lambda item: severity_rank.get(item.severity, 3))[0]


def _metric_line(metric: Metric) -> str:
    return f"- {metric.label}: {_format_value(metric)}"


def _supporting_metric_lines(metrics: dict, report: DailyReport, *, limit: int = 3) -> list[str]:
    preferred_keys = (
        "revenue_today",
        "revenue_today_tn",
        "tiendanube.revenue_today",
        "tn_revenue_today",
        "revenue_today_ml",
        "mercadolibre.revenue_today",
        "ml_revenue_today",
        "orders_today",
        "ad_spend_today",
        "stock_units",
        "unanswered_conversations",
    )
    selected: list[Metric] = []
    seen: set[str] = set()
    for key in preferred_keys:
        metric = metrics.get(key)
        if metric is not None and metric.key not in seen:
            selected.append(metric)
            seen.add(metric.key)
        if len(selected) >= limit:
            break
    for metric in report.metrics:
        if len(selected) >= limit:
            break
        if metric.key not in seen:
            selected.append(metric)
            seen.add(metric.key)
    return [_metric_line(metric) for metric in selected]


def _operator_priority_line(report: DailyReport) -> str:
    insight = _primary_insight(report)
    if insight is None:
        if report.metrics:
            return "Prioridad: sin urgencias hoy."
        return "Prioridad: sin recomendación todavía."
    return "Prioridad: " + _ensure_sentence(insight.recommended_action)


def _summary_lines(report: DailyReport) -> list[str]:
    insight = _primary_insight(report)
    if insight is None:
        if report.metrics:
            return ["No hay alertas críticas con los datos disponibles."]
        return ["No hay métricas cargadas. No se envían recomendaciones sobre datos incompletos."]
    return [_ensure_sentence(f"{insight.title}: {insight.explanation}")]


def _secondary_line(report: DailyReport, primary: object | None) -> str | None:
    for insight in report.insights:
        if insight is primary:
            continue
        return f"Secundario: {_ensure_sentence(insight.title)}"
    return None


def compose_daily_report_text(report: DailyReport) -> str:
    """Compose the Hito 0 WhatsApp report in a dry operator tone.

    The production message must read like a bounded morning operator brief for
    Juan: no assistant branding, no emoji, one priority, only action-relevant
    facts, and a compact source line so the owner can see why the report said
    what it said.
    """

    mkeys = _metrics_by_key(report)
    primary = _primary_insight(report)
    partial = not report.metrics
    header = f"{_business_label(report.business_name)} · {report.report_date.isoformat()}"
    if partial:
        header += " · partial"

    lines = [
        header,
        _operator_priority_line(report),
        "",
        *_summary_lines(report),
    ]

    fact_lines = _supporting_metric_lines(mkeys, report)
    if fact_lines:
        lines.append("")
        lines.extend(fact_lines)

    channel_lines = _canales_section(mkeys)
    if channel_lines:
        lines.extend(line.replace("📦 ", "") for line in channel_lines)

    ad_lines = _ads_section(mkeys)
    if ad_lines:
        lines.extend(line.replace("📣 ", "") for line in ad_lines)

    secondary = _secondary_line(report, primary)
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

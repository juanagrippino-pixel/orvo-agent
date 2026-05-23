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
        return "Fuentes: sin fuentes"
    return "Fuentes: " + ", ".join(labels)


_SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


_FACT_KEYS_BY_PRIORITY = (
    "revenue_today",
    "revenue_baseline",
    "revenue_today_tn",
    "revenue_today_ml",
    "tiendanube.revenue_today",
    "mercadolibre.revenue_today",
    "orders_today",
    "orders_today_tn",
    "orders_today_ml",
    "stock_units",
    "ad_spend_today",
    "unanswered_conversations",
)


_ACTION_PREFIXES = ("revisar", "verific", "pausar", "responder", "prioriz", "control", "confirm", "frenar")


def _primary_insight(report: DailyReport):
    if not report.insights:
        return None
    return sorted(report.insights, key=lambda item: _SEVERITY_RANK[item.severity])[0]


def _priority_line(report: DailyReport) -> str:
    insight = _primary_insight(report)
    if insight is None:
        return "Prioridad: no hay urgencia hoy."

    title = insight.title.lower()
    action = insight.recommended_action.strip()
    action_lc = action.lower()
    if "stock" in title and "ads" in title:
        return "Prioridad: pausar ads a productos con stock bajo."
    if "stock" in title:
        return "Prioridad: revisar stock antes de empujar ventas."
    if "sin ventas" in title or "sin ventas" in insight.explanation.lower():
        return "Prioridad: verificar tienda y checkout."
    if "roas" in title or "ads" in title or "publicidad" in title:
        return "Prioridad: revisar gasto de ads antes de escalar."
    if "ventas" in title and ("debajo" in title or "bajo" in title or "caída" in title):
        return "Prioridad: revisar checkout y pagos primero."
    if "conversaciones" in title or "chats" in title or "mensajes" in title:
        return "Prioridad: responder consultas de compra primero."

    if action and action_lc.startswith(_ACTION_PREFIXES):
        first_sentence = action.split(".", 1)[0].strip()
        if len(first_sentence) <= 90:
            return f"Prioridad: {first_sentence[0].lower() + first_sentence[1:]}."
    return "Prioridad: revisar el punto marcado abajo."


def _normalize_business_name(name: str) -> str:
    clean = name.strip()
    if clean.casefold() == "artemea":
        return "ARTEMEA"
    return clean


def _fact_metrics(report: DailyReport) -> list[Metric]:
    by_key = _metrics_by_key(report)
    selected: list[Metric] = []

    insight = _primary_insight(report)
    if insight is not None:
        insight_sources = {evidence.source for evidence in insight.evidence}
        for key in _FACT_KEYS_BY_PRIORITY:
            metric = by_key.get(key)
            if metric is None:
                continue
            if any(evidence.source in insight_sources for evidence in metric.evidence):
                selected.append(metric)
            if len(selected) == 3:
                return selected

    for key in _FACT_KEYS_BY_PRIORITY:
        metric = by_key.get(key)
        if metric is not None and metric not in selected:
            selected.append(metric)
        if len(selected) == 3:
            break
    if len(selected) < 3:
        for metric in report.metrics:
            if metric not in selected:
                selected.append(metric)
            if len(selected) == 3:
                break
    return selected


def _summary_line(report: DailyReport) -> str:
    insight = _primary_insight(report)
    if insight is None:
        return "Sin problema crítico detectado con los datos disponibles."
    return f"{insight.title}: {insight.explanation.rstrip('.')}."


def _derived_fact_lines(report: DailyReport) -> list[str]:
    metrics = _metrics_by_key(report)
    lines: list[str] = []
    tn_val = _metric_float(metrics, _TN_REVENUE_KEYS)
    ml_val = _metric_float(metrics, _ML_REVENUE_KEYS)
    if tn_val is not None and ml_val is not None:
        lines.append(f"- Total canales: {_format_ars(tn_val + ml_val)}")

    ad = metrics.get("ad_spend_today")
    if ad is not None:
        spend = float(ad.value)
        revenue = sum(
            value
            for value in (
                _metric_float(metrics, _TN_REVENUE_KEYS),
                _metric_float(metrics, _ML_REVENUE_KEYS),
                _metric_float(metrics, ("revenue_today",)),
            )
            if value is not None
        )
        if spend > 0 and revenue > 0:
            lines.append(f"- ROAS estimado: {revenue / spend:.1f}x")
    return lines


def _secondary_line(report: DailyReport) -> str | None:
    primary = _primary_insight(report)
    for insight in sorted(report.insights, key=lambda item: _SEVERITY_RANK[item.severity]):
        if insight is primary:
            continue
        if insight.severity in {"critical", "warning"}:
            return f"Secundario: {insight.title}."
    return None


def compose_daily_report_text(report: DailyReport) -> str:
    """Compose the Hito 0 WhatsApp operator brief.

    The output is intentionally dry and deterministic: priority first, a short
    explanation, up to three facts, and one source line. No branding, emoji, or
    assistant-like language is added because this is meant for Juan's 08:00
    Argentina owner report.
    """

    lines = [
        f"{_normalize_business_name(report.business_name)} · {report.report_date.isoformat()}",
        _priority_line(report),
        "",
        _summary_line(report),
    ]

    fact_lines = _derived_fact_lines(report)
    for metric in _fact_metrics(report):
        metric_line = f"- {metric.label}: {_format_value(metric)}"
        if metric_line not in fact_lines:
            fact_lines.append(metric_line)
        if len(fact_lines) == 3:
            break
    if fact_lines:
        lines.append("")
        lines.extend(fact_lines)

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

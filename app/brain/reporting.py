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
        for insight in report.insights:
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


def _shorten_sentence(text: str, max_chars: int) -> str:
    """Return a compact, human-readable sentence within max_chars."""
    clean = " ".join(str(text).split())
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3].rstrip() + "..."


def _insight_prefix(severity: str) -> tuple[str, str]:
    if severity == "critical":
        return "🔴", "Urgente:"
    if severity == "warning":
        return "🟡", "Acción:"
    return "🔵", "Acción:"


def compose_whatsapp_preview_text(report: DailyReport, max_chars: int = 1000) -> str:
    """Compose a clean WhatsApp demo preview that fits a practical budget.

    Unlike :func:`compose_daily_report_text`, this is optimized for sales demos
    and owner-facing WhatsApp previews: it keeps the urgent recommended action
    visible, avoids mid-sentence truncation, and still includes compact sources.
    """

    def build(*, metric_limit: int | None = None, insight_limit: int | None = None) -> str:
        lines = [
            f"🧠 Orvo Brain — {report.business_name}",
            f"Reporte diario · {report.report_date.isoformat()}",
            "",
            "📊 Métricas",
        ]

        metrics = report.metrics if metric_limit is None else report.metrics[:metric_limit]
        if metrics:
            for metric in metrics:
                lines.append(f"- {metric.label}: {_format_value(metric)}")
            if metric_limit is not None and len(report.metrics) > metric_limit:
                lines.append(f"- +{len(report.metrics) - metric_limit} métricas en reporte completo")
        else:
            lines.append("- Sin métricas cargadas todavía")

        ordered_insights = sorted(
            report.insights,
            key=lambda i: {"critical": 0, "warning": 1, "info": 2}.get(i.severity, 3),
        )
        insights = ordered_insights if insight_limit is None else ordered_insights[:insight_limit]

        lines.extend(["", "🚨 Alertas"])
        if insights:
            for insight in insights:
                prefix, action_label = _insight_prefix(insight.severity)
                title = _shorten_sentence(insight.title, 72)
                action = _shorten_sentence(insight.recommended_action, 180)
                lines.append(f"{prefix} {title}")
                lines.append(f"   {action_label} {action}")
            if insight_limit is not None and len(ordered_insights) > insight_limit:
                lines.append(f"🔵 +{len(ordered_insights) - insight_limit} alertas en reporte completo")
        else:
            lines.append("✅ Sin alertas críticas por ahora.")

        lines.extend(["", _compact_sources(report)])
        return "\n".join(lines)

    candidates = [
        build(),
        build(metric_limit=6, insight_limit=3),
        build(metric_limit=5, insight_limit=2),
        build(metric_limit=4, insight_limit=1),
    ]
    for candidate in candidates:
        if len(candidate) <= max_chars:
            return candidate

    suffix = "\n... ver reporte completo"
    budget = max_chars - len(suffix)
    kept: list[str] = []
    total = 0
    for line in candidates[-1].splitlines():
        extra = len(line) + (1 if kept else 0)
        if total + extra > budget:
            break
        kept.append(line)
        total += extra
    return "\n".join(kept) + suffix


def truncate_for_whatsapp(text: str, max_chars: int = 1000) -> str:
    """Trim a report to fit WhatsApp's practical reading budget.

    Keeps the text unchanged if under max_chars. Otherwise trims and appends
    '... (ver reporte completo)'.
    """
    if len(text) <= max_chars:
        return text
    suffix = "... (ver reporte completo)"
    return text[: max_chars - len(suffix)] + suffix

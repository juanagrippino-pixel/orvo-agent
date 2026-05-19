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


def _evidence_lines(report: DailyReport) -> list[str]:
    seen: set[tuple[str, str]] = set()
    sources: list[Evidence] = []
    for metric in report.metrics:
        for evidence in metric.evidence:
            key = (evidence.source, evidence.label)
            if key not in seen:
                sources.append(evidence)
                seen.add(key)
    for insight in report.insights:
        for evidence in insight.evidence:
            key = (evidence.source, evidence.label)
            if key not in seen:
                sources.append(evidence)
                seen.add(key)
    return [f"- {source.label} ({source.source})" for source in sources]


def compose_daily_report_text(report: DailyReport) -> str:
    """Compose a short, cited Spanish daily report for a business owner."""

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

    lines.extend(["", "🚨 Alertas"])
    if report.insights:
        for insight in report.insights:
            prefix = "🔴" if insight.severity == "critical" else "🟡" if insight.severity == "warning" else "ℹ️"
            lines.append(f"{prefix} {insight.title}: {insight.explanation}")
            lines.append(f"   Acción: {insight.recommended_action}")
    else:
        lines.append("✅ Sin alertas críticas por ahora.")

    source_lines = _evidence_lines(report)
    lines.extend(["", "📌 Fuentes"])
    lines.extend(source_lines or ["- Sin fuentes cargadas"])

    return "\n".join(lines)

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



def _severity_rank(severity: str) -> int:
    return {"critical": 0, "warning": 1, "info": 2}.get(severity, 3)


def _primary_insight(report: DailyReport):
    if not report.insights:
        return None
    return sorted(enumerate(report.insights), key=lambda item: (_severity_rank(item[1].severity), item[0]))[0][1]


def _first_sentence(text: str) -> str:
    stripped = " ".join(text.split())
    for marker in (". ", "; "):
        if marker in stripped:
            return stripped.split(marker, 1)[0].rstrip(".;") + "."
    return stripped if stripped.endswith(".") else stripped + "."


def _operator_action(action: str) -> str:
    text = _first_sentence(action)
    replacements = {
        "Revisá": "Revisar",
        "Verificá": "Verificar",
        "Priorizá": "Priorizar",
        "Pausá": "Pausar",
        "Respondé": "Responder",
        "Considerá": "Considerar",
    }
    for source, target in replacements.items():
        if text.startswith(source):
            text = target + text[len(source):]
            break
    return text[:1].lower() + text[1:]


def _evidence_keys_for_insight(report: DailyReport, insight) -> set[tuple[str, str]]:
    if insight is None:
        return set()
    return {(item.source, item.label) for item in insight.evidence}


def _operator_fact_metrics(report: DailyReport, insight) -> list[Metric]:
    evidence_keys = _evidence_keys_for_insight(report, insight)
    preferred = {
        "stock_units": 0,
        "ad_spend_today": 1,
        "revenue_today": 2,
        "revenue_today_tn": 3,
        "tiendanube.revenue_today": 3,
        "orders_today": 4,
        "orders_today_tn": 5,
        "unanswered_conversations": 6,
        "revenue_baseline": 7,
        "revenue_today_ml": 8,
        "mercadolibre.revenue_today": 8,
    }

    def sort_key(metric: Metric) -> tuple[int, int]:
        cited = any((ev.source, ev.label) in evidence_keys for ev in metric.evidence)
        return (0 if cited else 1, preferred.get(metric.key, 50))

    return sorted(report.metrics, key=sort_key)[:3]


def compose_daily_report_text(report: DailyReport) -> str:
    """Compose the Hito 0 WhatsApp owner brief in a dry operator tone."""

    primary = _primary_insight(report)
    partial = " · parcial" if not report.metrics else ""
    lines = [f"{report.business_name} · {report.report_date.isoformat()}{partial}"]

    if primary is None:
        lines.extend(["Prioridad: no hay urgencia operativa hoy.", ""])
        if report.metrics:
            lines.append("No hay alertas críticas con los datos disponibles.")
        else:
            lines.append("Sin datos cargados. Recomendaciones omitidas.")
    else:
        lines.extend([f"Prioridad: {_operator_action(primary.recommended_action)}", ""])
        lines.append(_first_sentence(primary.explanation))

    facts = _operator_fact_metrics(report, primary)
    if facts:
        for metric in facts:
            lines.append(f"- {metric.label}: {_format_value(metric)}")

    if primary is not None:
        secondary = [insight for insight in report.insights if insight is not primary and insight.severity in {"critical", "warning"}]
        if secondary:
            lines.append(f"Secundario: {_first_sentence(secondary[0].title)}")

    lines.append(_compact_sources(report))
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

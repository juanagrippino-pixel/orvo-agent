"""Report composition for WhatsApp-first Orvo Brain output."""

from datetime import date, datetime, timezone
from typing import Iterable

from app.brain.models import DailyReport, Evidence, Metric
from app.brain.operational_cases import OperationalCase, owner_facing_actionable_cases
from app.brain.security.redaction import redact_text


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


def _case_order(case: OperationalCase) -> tuple[int, int, str, str]:
    return (_SEVERITY_ORDER.get(case.severity, 9), -case.priority_score, case.opened_at.isoformat(), case.case_id)


def _case_sources(case: OperationalCase) -> list[str]:
    seen: set[str] = set()
    labels: list[str] = []
    for snapshot in case.evidence_snapshots:
        label = snapshot.source_label or snapshot.source
        if label and label not in seen:
            labels.append(label)
            seen.add(label)
    return labels


def _case_metric_lines(case: OperationalCase, *, max_metrics: int = 2) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for snapshot in case.evidence_snapshots:
        for metric in snapshot.metrics:
            label = metric.label or metric.metric_key
            if label in seen:
                continue
            seen.add(label)
            if metric.value is None:
                continue
            value = f"{metric.value:g}" if isinstance(metric.value, (int, float)) else str(metric.value)
            suffix = f" {metric.unit}" if metric.unit else ""
            lines.append(f"{label}: {value}{suffix}")
            if len(lines) >= max_metrics:
                return lines
    return lines


def _case_is_degraded(case: OperationalCase) -> bool:
    return any(snapshot.freshness_state in {"stale", "degraded", "missing"} for snapshot in case.evidence_snapshots)


def _utc_date(value: datetime) -> date:
    return value.astimezone(timezone.utc).date()


def _latest_reopen_at(case: OperationalCase) -> datetime | None:
    reopens = [event.created_at for event in case.timeline if event.event_type == "case_reopened"]
    return max(reopens) if reopens else None


def _format_age_label(verb_today: str, verb_past: str, reference: date, anchor: date) -> str:
    delta = (reference - anchor).days
    if delta <= 0:
        return f"{verb_today} hoy"
    if delta == 1:
        return f"{verb_past} hace 1 día"
    return f"{verb_past} hace {delta} días"


def _case_age_label(case: OperationalCase, report_date: date) -> str:
    reopen_at = _latest_reopen_at(case)
    if reopen_at is not None:
        return _format_age_label("Reabierto", "Reabierto", report_date, _utc_date(reopen_at))
    return _format_age_label("Nuevo", "Abierto", report_date, _utc_date(case.opened_at))


def _case_status_line(case: OperationalCase, report_date: date | None) -> str | None:
    parts: list[str] = []
    if report_date is not None:
        parts.append(_case_age_label(case, report_date))
    if case.status == "acknowledged":
        parts.append("✓ Visto")
    if not parts:
        return None
    return "   Estado: " + " · ".join(parts)


def compose_owner_case_brief(
    business_name: str,
    cases: Iterable[OperationalCase],
    *,
    report_date: date | None = None,
    max_cases: int = 3,
) -> str:
    """Compose a WhatsApp-sized owner brief from canonical open Operational Cases.

    This is a projection only: case state/evidence remains owned by the case
    store. The text is intentionally short and fully redacted before returning.
    """

    actionable = owner_facing_actionable_cases(cases)
    actionable = sorted(actionable, key=_case_order)
    visible_cases = actionable[:max_cases]
    date_suffix = f" · {report_date.isoformat()}" if report_date else ""
    lines = [f"🧠 Orvo — {business_name}", f"Brief operativo{date_suffix}", ""]

    if not actionable:
        lines.append("✅ Sin temas operativos abiertos por ahora.")
        return redact_text("\n".join(lines)) or "[REDACTED]"

    total_plural = "tema operativo abierto" if len(actionable) == 1 else "temas operativos abiertos"
    if len(actionable) > len(visible_cases):
        shown_plural = "principal" if len(visible_cases) == 1 else "principales"
        lines.append(f"Hay {len(actionable)} {total_plural}; te muestro los {len(visible_cases)} {shown_plural}:")
    else:
        review_plural = "tema operativo" if len(actionable) == 1 else "temas operativos"
        lines.append(f"Hoy hay {len(actionable)} {review_plural} para revisar:")

    for index, case in enumerate(visible_cases, start=1):
        prefix = "🔴" if case.severity == "critical" else "🟡" if case.severity == "warning" else "ℹ️"
        lines.extend(["", f"{index}. {prefix} {case.title}", f"   Caso: {case.case_id}"])
        status_line = _case_status_line(case, report_date)
        if status_line:
            lines.append(status_line)
        sources = _case_sources(case)
        if sources:
            lines.append("   Evidencia: " + " · ".join(sources))
        metric_lines = _case_metric_lines(case)
        if metric_lines:
            lines.append("   Métricas: " + " · ".join(metric_lines))
        if _case_is_degraded(case):
            lines.append("   ⚠️ Evidencia degradada: revisar frescura antes de decidir.")
        recommended_action = case.metadata.get("recommended_action")
        if recommended_action:
            lines.append(f"   Acción sugerida: {recommended_action}")

    return redact_text("\n".join(lines)) or "[REDACTED]"


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

    return redact_text("\n".join(lines)) or "[REDACTED]"


def truncate_for_whatsapp(text: str, max_chars: int = 1000) -> str:
    """Trim a report to fit WhatsApp's practical reading budget.

    Keeps the text unchanged if under max_chars. Otherwise trims and appends
    '... (ver reporte completo)'.
    """
    if len(text) <= max_chars:
        return text
    suffix = "... (ver reporte completo)"
    return text[: max_chars - len(suffix)] + suffix

"""Deterministic Orvo Brain insight engine.

LLMs may later explain these findings, but the business logic and citations
must stay deterministic.
"""

from app.brain.models import Evidence, Insight, Metric


def _metric_map(metrics: list[Metric]) -> dict[str, Metric]:
    return {metric.key: metric for metric in metrics}


def _to_float(metric: Metric | None) -> float | None:
    if metric is None:
        return None
    try:
        return float(metric.value)
    except (TypeError, ValueError):
        return None


def _merge_evidence(*metrics: Metric | None) -> list[Evidence]:
    evidence: list[Evidence] = []
    seen: set[tuple[str, str]] = set()
    for metric in metrics:
        if metric is None:
            continue
        for item in metric.evidence:
            key = (item.source, item.label)
            if key not in seen:
                evidence.append(item)
                seen.add(key)
    return evidence


def generate_insights(
    metrics: list[Metric],
    *,
    revenue_drop_threshold: float = 0.15,
    stock_threshold: int = 5,
    unanswered_threshold: int = 5,
) -> list[Insight]:
    """Generate operational insights from cited canonical metrics."""

    by_key = _metric_map(metrics)
    insights: list[Insight] = []

    revenue_today = _to_float(by_key.get("revenue_today"))
    revenue_baseline = _to_float(by_key.get("revenue_baseline"))
    if revenue_today is not None and revenue_baseline and revenue_baseline > 0:
        drop_ratio = (revenue_baseline - revenue_today) / revenue_baseline
        if drop_ratio >= revenue_drop_threshold:
            pct = round(drop_ratio * 100)
            insights.append(
                Insight(
                    severity="warning",
                    title=f"Ventas {pct}% debajo del promedio",
                    explanation="Las ventas de hoy están por debajo del promedio reciente.",
                    recommended_action="Revisá campañas activas, productos principales y mensajes pendientes antes de cerrar el día.",
                    evidence=_merge_evidence(by_key.get("revenue_today"), by_key.get("revenue_baseline")),
                )
            )

    stock_units = _to_float(by_key.get("stock_units"))
    if stock_units is not None and stock_units <= stock_threshold:
        insights.append(
            Insight(
                severity="critical",
                title="Stock crítico",
                explanation=f"Quedan {int(stock_units)} unidades disponibles en productos monitoreados.",
                recommended_action="Priorizá reposición o pausá campañas que empujen productos con bajo stock.",
                evidence=_merge_evidence(by_key.get("stock_units")),
            )
        )

    unanswered = _to_float(by_key.get("unanswered_conversations"))
    if unanswered is not None and unanswered >= unanswered_threshold:
        insights.append(
            Insight(
                severity="warning",
                title="Conversaciones sin responder",
                explanation=f"Hay {int(unanswered)} conversaciones pendientes que pueden frenar ventas.",
                recommended_action="Responder primero consultas de compra, envíos, talles/precios y reclamos recientes.",
                evidence=_merge_evidence(by_key.get("unanswered_conversations")),
            )
        )

    return insights

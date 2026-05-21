"""Sales-oriented demo assets for Orvo Brain prospects.

The one-pager is deterministic and derived from the same seeded demo reports as
``scripts/demo_report.py`` so sales copy stays aligned with product output.
"""

from __future__ import annotations

from app.brain.demo_scenarios import SCENARIOS, build_demo_report
from app.brain.reporting import compose_daily_report_text, truncate_for_whatsapp


def _format_ars(value: float) -> str:
    return f"ARS {value:,.0f}".replace(",", ".")


def _metric_value(report, key: str) -> float | None:
    for metric in report.metrics:
        if metric.key == key:
            try:
                return float(metric.value)
            except (TypeError, ValueError):
                return None
    return None


def _scenario_proof_line(scenario_id: str) -> str:
    scenario = SCENARIOS[scenario_id]
    report = build_demo_report(scenario_id)
    whatsapp_text = truncate_for_whatsapp(compose_daily_report_text(report))

    revenue = _metric_value(report, "revenue_today")
    if revenue is None:
        tn = _metric_value(report, "revenue_today_tn") or 0
        ml = _metric_value(report, "revenue_today_ml") or 0
        revenue = tn + ml if (tn or ml) else None

    severity_rank = {"critical": 0, "warning": 1}
    severe = sorted(
        (insight for insight in report.insights if insight.severity in severity_rank),
        key=lambda insight: severity_rank[insight.severity],
    )
    proof = severe[0].title if severe else "Sin alertas críticas"
    revenue_text = _format_ars(revenue) if revenue is not None else "sin revenue cargado"
    return (
        f"| `{scenario_id}` | {scenario['title']} | {revenue_text} | "
        f"{proof} | {len(whatsapp_text)} caracteres |"
    )


def build_demo_sales_onepager() -> str:
    """Build a concise Spanish sales one-pager for seeded Orvo Brain demos."""

    scenario_lines = [
        "| Demo | Caso PyME | Prueba de negocio | Insight que se ve en WhatsApp | Tamaño |",
        "|---|---|---:|---|---:|",
    ]
    scenario_lines.extend(_scenario_proof_line(sid) for sid in SCENARIOS)

    return "\n".join([
        "# Orvo Brain — demo comercial",
        "",
        "## Para vender en 2 minutos",
        "Orvo Brain convierte datos de Tiendanube, MercadoLibre, Meta Ads, CSV o Sheets en un reporte diario de WhatsApp para dueños de PyMEs argentinas y LatAm.",
        "",
        "**Promesa:** detectar plata en riesgo antes de que termine el día: stock crítico, mensajes sin responder, campañas gastando sin ventas y desbalances entre canales.",
        "",
        "## ROI que entiende el dueño",
        "- Menos ventas perdidas: prioriza reposición, respuestas y campañas activas.",
        "- Menos horas mirando dashboards: el resumen llega donde ya trabaja el negocio, WhatsApp.",
        "- Más confianza: cada métrica e insight viene citado con su fuente, sin inventar números.",
        "",
        "## Demos sembradas listas para mostrar",
        *scenario_lines,
        "",
        "## Guion corto",
        "1. Ejecutá `python scripts/demo_report.py` y mostrá los tres mensajes de WhatsApp.",
        "2. Para una conversación comercial, ejecutá `python scripts/demo_report.py --sales-onepager` y usá esta página como resumen.",
        "3. Cerrá con el caso crítico: si hay Stock crítico mientras Meta Ads sigue gastando, Orvo Brain avisa en el día y propone la acción.",
        "",
        "## Qué pedir para piloto",
        "Una fuente inicial: CSV/Sheets exportado, Tiendanube, MercadoLibre o Meta Ads. No se necesitan credenciales para ver esta demo.",
    ])

"""Deterministic demo scenarios for Orvo Brain — used by the one-command demo.

Each scenario produces a fully-cited DailyReport with realistic PyME numbers
that exercise different parts of the insight engine and report formatter.
"""

from __future__ import annotations

from datetime import date

from app.brain.adapters.sample import build_daily_report_from_payload


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, dict] = {
    "pyme-normal": {
        "title": "Reporte normal — día bueno",
        "description": (
            "Ventas por encima del promedio, stock sano, bajo gasto en ads. "
            "Muestra un día típico sin alertas críticas."
        ),
        "payload": {
            "business_name": "Artemea — Flores",
            "report_date": "2026-05-20",
            "source_label": "Demo Tiendanube",
            "metrics": {
                "revenue_today": 285_000,
                "revenue_baseline": 240_000,
                "orders_today": 19,
                "stock_units": 180,
                "unanswered_conversations": 2,
                "ad_spend_today": 18_500,
            },
        },
    },
    "pyme-stock-crisis": {
        "title": "Stock crítico + ads activos — alerta urgente",
        "description": (
            "Ventas en caída, stock de solo 3 unidades, 12 conversaciones sin "
            "responder y $25.000 gastados en ads. Demuestra el valor de la "
            "detección temprana para evitar pérdidas."
        ),
        "payload": {
            "business_name": "Café de Barrio — Colegiales",
            "report_date": "2026-05-20",
            "source_label": "Demo Tiendanube + Meta Ads",
            "metrics": {
                "revenue_today": 95_000,
                "revenue_baseline": 180_000,
                "stock_units": 3,
                "unanswered_conversations": 12,
                "ad_spend_today": 25_000,
            },
        },
    },
    "pyme-multi-canal": {
        "title": "Multi-canal — Tiendanube + MercadoLibre + Meta Ads",
        "description": (
            "Negocio con ventas en dos canales y gasto en publicidad. Muestra "
            "el balance de canales, ROAS estimado y detección de desbalance."
        ),
        "payload": {
            "business_name": "ModaSud — Buenos Aires",
            "report_date": "2026-05-20",
            "source_label": "Demo Multi-canal",
            "metrics": {
                "revenue_today_tn": 320_000,
                "revenue_today_ml": 510_000,
                "orders_today_tn": 22,
                "orders_today_ml": 35,
                "stock_units": 95,
                "unanswered_conversations": 4,
                "ad_spend_today": 42_000,
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_demo_report(scenario_id: str):
    """Build a DailyReport for a named demo scenario.

    Raises KeyError if the scenario_id is not found.
    """
    scenario = SCENARIOS[scenario_id]
    return build_daily_report_from_payload(scenario["payload"])


def build_all_demo_reports():
    """Build DailyReports for every scenario, preserving order."""
    return [(sid, build_demo_report(sid)) for sid in SCENARIOS]


def _format_ars(value: float | int) -> str:
    """Format Argentine pesos compactly for prospect-facing demo copy."""
    return f"ARS {value:,.0f}".replace(",", ".")


def _metric_values(report) -> dict[str, float | int | str]:
    return {metric.key: metric.value for metric in report.metrics}


def build_demo_sales_summary(scenario_id: str) -> dict:
    """Build a prospect-facing sales summary for a demo scenario.

    The daily WhatsApp report proves the product output; this summary gives a
    seller or founder a concise ROI hook for demos, DMs, and follow-up notes.
    It stays deterministic and only uses metrics already present in the seeded
    scenario report.
    """

    scenario = SCENARIOS[scenario_id]
    report = build_demo_report(scenario_id)
    metrics = _metric_values(report)

    impact_estimate = 0.0
    proof_points: list[str] = []

    revenue_today = metrics.get("revenue_today")
    revenue_baseline = metrics.get("revenue_baseline")
    if isinstance(revenue_today, (int, float)) and isinstance(revenue_baseline, (int, float)):
        revenue_gap = max(float(revenue_baseline) - float(revenue_today), 0.0)
        if revenue_gap > 0:
            impact_estimate += revenue_gap
            proof_points.append(
                f"{_format_ars(revenue_gap)} de ventas vs promedio reciente detectadas antes del cierre."
            )
        else:
            proof_points.append(
                f"Ventas {_format_ars(revenue_today)}: por encima del promedio reciente."
            )

    stock_units = metrics.get("stock_units")
    ad_spend = metrics.get("ad_spend_today")
    if isinstance(stock_units, (int, float)) and isinstance(ad_spend, (int, float)):
        if stock_units <= 5 and ad_spend > 0:
            impact_estimate += float(ad_spend)
            proof_points.append(
                f"{_format_ars(ad_spend)} en ads activos con stock crítico ({int(stock_units)} unidades)."
            )
        elif ad_spend > 0:
            proof_points.append(f"Ads monitoreados: {_format_ars(ad_spend)} de gasto diario bajo control.")

    unanswered = metrics.get("unanswered_conversations")
    if isinstance(unanswered, (int, float)) and unanswered > 0:
        proof_points.append(f"{int(unanswered)} conversaciones sin responder priorizadas para recuperar ventas.")

    tn_revenue = metrics.get("revenue_today_tn")
    ml_revenue = metrics.get("revenue_today_ml")
    if isinstance(tn_revenue, (int, float)) and isinstance(ml_revenue, (int, float)):
        total = float(tn_revenue) + float(ml_revenue)
        proof_points.append(
            f"Visión multi-canal: Tiendanube + MercadoLibre suman {_format_ars(total)} en el día."
        )

    if not proof_points:
        proof_points.append("Reporte diario listo para mostrar control operativo sin planillas manuales.")

    formatted_impact = _format_ars(impact_estimate)
    if impact_estimate > 0:
        headline = f"Detecta {formatted_impact} de impacto operativo accionable en 1 reporte."
    else:
        headline = "Muestra control diario y evidencia confiable sin integraciones manuales."

    return {
        "scenario_id": scenario_id,
        "business_name": report.business_name,
        "title": scenario["title"],
        "headline": headline,
        "impact_estimate": int(impact_estimate),
        "proof_points": proof_points,
        "next_step": "Mostrar el WhatsApp demo y cerrar una prueba con datos reales del negocio.",
    }


def format_demo_sales_summary(summary: dict) -> str:
    """Format a sales summary as concise Spanish copy for demos or DMs."""

    proof = "\n".join(f"- {item}" for item in summary["proof_points"][:4])
    return "\n".join(
        [
            f"💰 Gancho comercial — {summary['business_name']}",
            summary["headline"],
            "",
            "Prueba:",
            proof,
            "",
            f"Siguiente paso: {summary['next_step']}",
        ]
    )

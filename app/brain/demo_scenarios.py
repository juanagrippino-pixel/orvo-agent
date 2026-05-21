"""Deterministic demo scenarios for Orvo Brain — used by the one-command demo.

Each scenario produces a fully-cited DailyReport with realistic PyME numbers
that exercise different parts of the insight engine and report formatter.
"""

from __future__ import annotations

from datetime import date

from app.brain.adapters.sample import build_daily_report_from_payload
from app.brain.reporting import compose_daily_report_text, truncate_for_whatsapp


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
        "buyer_pain": "No sé si el día viene bien hasta revisar cada canal manualmente.",
        "sales_angle": "Muestra tranquilidad operativa: Orvo confirma que no hay urgencias y resume los números clave.",
        "demo_prompt": "¿Cuánto tiempo perdés hoy chequeando si todo está normal?",
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
        "buyer_pain": "Estoy pagando campañas mientras me quedo sin stock y pierdo consultas calientes.",
        "sales_angle": "Muestra ROI inmediato: detectar stock crítico + ads activos antes de seguir quemando presupuesto.",
        "demo_prompt": "¿Quién te avisa hoy, por WhatsApp, que tenés que pausar ads o reponer antes de perder ventas?",
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
        "buyer_pain": "Tiendanube, MercadoLibre y Meta Ads no me dicen juntos qué canal está empujando el negocio.",
        "sales_angle": "Muestra control multi-canal en una sola lectura: ventas por canal, ROAS y desbalances accionables.",
        "demo_prompt": "¿Hoy podés ver en un minuto si MercadoLibre está compensando una caída de tu tienda propia?",
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


def build_demo_sales_brief(scenario_id: str) -> dict:
    """Build a deterministic seller-facing brief for a demo scenario.

    The brief is not an LLM summary: it is derived from the seeded report and
    scenario metadata so a sales call can show the exact PyME pain, WhatsApp
    output size, top alerts, and next actions without inventing metrics.
    """
    scenario = SCENARIOS[scenario_id]
    report = build_demo_report(scenario_id)
    whatsapp_text = truncate_for_whatsapp(compose_daily_report_text(report))

    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    ordered_insights = sorted(report.insights, key=lambda item: severity_rank[item.severity])
    top_alerts = [f"{insight.severity.upper()}: {insight.title}" for insight in ordered_insights[:3]]
    next_actions = [insight.recommended_action for insight in ordered_insights[:3]]

    return {
        "scenario_id": scenario_id,
        "title": scenario["title"],
        "business_name": report.business_name,
        "buyer_pain": scenario["buyer_pain"],
        "sales_angle": scenario["sales_angle"],
        "demo_prompt": scenario["demo_prompt"],
        "whatsapp_chars": len(whatsapp_text),
        "top_alerts": top_alerts,
        "next_actions": next_actions,
    }

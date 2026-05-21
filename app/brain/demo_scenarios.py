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
        "sales_summary": {
            "persona": "Dueña de tienda con ventas saludables pero poco tiempo para revisar métricas",
            "pain": "Hoy vende bien, pero todavía depende de abrir Tiendanube, planillas y Meta Ads a mano.",
            "roi_hook": "Orvo convierte 10 minutos diarios de revisión manual en un WhatsApp con ventas, stock y ads ya priorizados.",
            "cta": "Mostrale este WhatsApp y preguntá: ¿querés recibirlo cada mañana antes de abrir el negocio?",
        },
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
        "sales_summary": {
            "persona": "Cafetería/retail con productos de alta rotación y campañas activas",
            "pain": "Está pagando tráfico mientras se queda sin stock y deja consultas calientes sin responder.",
            "roi_hook": "Una alerta temprana por WhatsApp ayuda a frenar gasto improductivo y recuperar ventas antes de que cierre el día.",
            "cta": "Mostrale la alerta roja y ofrecé configurar su primer reporte WhatsApp con stock + ads esta semana.",
        },
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
        "sales_summary": {
            "persona": "Marca PyME que vende por Tiendanube, MercadoLibre y pauta en Meta",
            "pain": "Las ventas están repartidas en canales y nadie mira ROAS, desbalance ni conversaciones en un solo lugar.",
            "roi_hook": "Orvo junta canales + ads en un WhatsApp accionable para decidir dónde empujar ventas mañana.",
            "cta": "Usá este WhatsApp como demo de control multi-canal y pedí acceso a Tiendanube/ML/Meta para un piloto.",
        },
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


def format_demo_sales_summary(scenario_id: str) -> str:
    """Return compact sales-talk-track copy for a demo scenario.

    The text is intentionally deterministic and prospect-facing so a seller can
    paste it into notes or read it before showing the WhatsApp output.
    """
    scenario = SCENARIOS[scenario_id]
    sales = scenario["sales_summary"]
    return "\n".join(
        [
            "💬 Para venderlo:",
            f"- Cliente ideal: {sales['persona']}",
            f"- Dolor: {sales['pain']}",
            f"- ROI: {sales['roi_hook']}",
            f"- CTA: {sales['cta']}",
        ]
    )

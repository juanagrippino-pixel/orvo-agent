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

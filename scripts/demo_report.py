#!/usr/bin/env python3
"""Orvo Brain — one-command demo report generator.

Run this to see exactly what PyME prospects receive on WhatsApp:

    python scripts/demo_report.py

Generates three realistic scenarios:
  1. Normal good day (no critical alerts)
  2. Stock crisis + active ads (urgent alerts)
  3. Multi-channel Tiendanube + MercadoLibre + Meta Ads

No API keys, no external services. All data is deterministic and seeded.

For a single scenario:
    python scripts/demo_report.py --scenario pyme-stock-crisis

Save outputs to files:
    python scripts/demo_report.py --save-dir examples/demo_output/

Generate a prospect-ready sales pack with README, WhatsApp samples and JSON evidence:
    python scripts/demo_report.py --sales-pack examples/demo_output/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brain.demo_scenarios import SCENARIOS, build_demo_report
from app.brain.reporting import compose_daily_report_text, truncate_for_whatsapp


def _divider():
    print("=" * 60)



def _format_money(value: float | int) -> str:
    """Format ARS-style amounts for prospect-facing demo copy."""
    return f"${value:,.0f}".replace(",", ".")


def _scenario_roi_note(scenario_id: str, report) -> str:
    """Return a deterministic, sales-safe ROI note for a scenario.

    These notes use only metrics present in the seeded report; they do not
    invent external benchmarks or customer results.
    """
    metrics = {metric.key: metric.value for metric in report.metrics}
    if scenario_id == "pyme-stock-crisis":
        ad_spend = metrics.get("ad_spend_today", 0)
        stock = metrics.get("stock_units", 0)
        unanswered = metrics.get("unanswered_conversations", 0)
        return (
            f"Evita quemar {_format_money(ad_spend)} en anuncios cuando quedan "
            f"solo {stock:.0f} unidades y {unanswered:.0f} chats sin responder."
        )
    if scenario_id == "pyme-multi-canal":
        tn = metrics.get("revenue_today_tn", 0)
        ml = metrics.get("revenue_today_ml", 0)
        total = tn + ml
        return (
            f"Unifica {_format_money(total)} vendidos entre Tiendanube y MercadoLibre "
            "para decidir dónde empujar stock y pauta hoy."
        )
    revenue = metrics.get("revenue_today", 0)
    baseline = metrics.get("revenue_baseline", 0)
    delta = revenue - baseline
    return (
        f"Muestra en 30 segundos si el día viene {_format_money(delta)} sobre el promedio "
        "y qué revisar antes de cerrar."
    )


def write_sales_pack(save_dir: Path) -> dict[str, dict[str, object]]:
    """Write a prospect-ready demo pack and return a manifest.

    The pack contains WhatsApp-ready `.txt` samples, cited JSON payloads, and a
    Spanish README with ROI talking points for a sales call. It uses only seeded
    deterministic data and never requires credentials.
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, object]] = {}
    readme_sections = [
        "# Orvo Brain — Pack de demo comercial",
        "",
        "Este directorio contiene salidas determinísticas listas para mostrar a PyMEs argentinas/LatAm: mensajes de WhatsApp, payloads con evidencia y un guion corto de venta.",
        "",
        "## Cómo usarlo en una venta",
        "",
        "1. Abrí el `.txt` del escenario más parecido al prospecto y mostrale el mensaje como si llegara por WhatsApp.",
        "2. Remarcá que cada alerta viene de métricas citadas en el `.json`, no de una alucinación de IA.",
        "3. Cerrá con el punto de ROI: menos ventas perdidas, menos pauta quemada y menos tiempo revisando paneles.",
        "",
        "## Escenarios incluidos",
        "",
    ]

    for scenario_id, scenario in SCENARIOS.items():
        report = build_demo_report(scenario_id)
        text = compose_daily_report_text(report)
        whatsapp_text = truncate_for_whatsapp(text)
        (save_dir / f"{scenario_id}.txt").write_text(whatsapp_text, encoding="utf-8")
        (save_dir / f"{scenario_id}.json").write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        roi_note = _scenario_roi_note(scenario_id, report)
        manifest[scenario_id] = {
            "title": scenario["title"],
            "business_name": report.business_name,
            "whatsapp_file": f"{scenario_id}.txt",
            "json_file": f"{scenario_id}.json",
            "whatsapp_chars": len(whatsapp_text),
            "roi_note": roi_note,
        }
        readme_sections.extend(
            [
                f"### {scenario_id} — {scenario['title']}",
                "",
                scenario["description"],
                "",
                f"- Negocio demo: {report.business_name}",
                f"- WhatsApp: `{scenario_id}.txt` ({len(whatsapp_text)} caracteres)",
                f"- Evidencia JSON: `{scenario_id}.json`",
                f"- ROI: {roi_note}",
                "",
            ]
        )

    readme_sections.extend(
        [
            "## Reproducir",
            "",
            "```bash",
            "python scripts/demo_report.py --sales-pack examples/demo_output",
            "```",
            "",
            "No usa APIs externas ni credenciales; todos los datos son sembrados y seguros para compartir.",
            "",
        ]
    )
    (save_dir / "README.md").write_text("\n".join(readme_sections), encoding="utf-8")
    return manifest

def print_scenario(scenario_id: str, *, save_dir: Path | None = None):
    scenario = SCENARIOS[scenario_id]
    report = build_demo_report(scenario_id)
    text = compose_daily_report_text(report)
    text_truncated = truncate_for_whatsapp(text)

    print()
    _divider()
    print(f"📋 {scenario['title']}")
    print(f"   {scenario['description']}")
    _divider()
    print()
    print(text_truncated)

    # WhatsApp budget info
    char_count = len(text_truncated)
    print()
    print(f"   📏 {char_count} caracteres{' (truncado)' if char_count != len(text) else ''} / 1000 presupuesto WhatsApp")
    print()

    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / f"{scenario_id}.txt").write_text(text_truncated, encoding="utf-8")
        (save_dir / f"{scenario_id}.json").write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"   💾 Guardado en {save_dir}/")

    if scenario_id != list(SCENARIOS)[-1]:
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orvo Brain — one-command demo report generator",
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        help="Run only one scenario (default: all)",
    )
    parser.add_argument(
        "--save-dir",
        type=str,
        default=None,
        help="Directory to save text/JSON outputs",
    )
    parser.add_argument(
        "--sales-pack",
        type=str,
        default=None,
        metavar="DIR",
        help="Write a prospect-ready sales pack (README + WhatsApp samples + JSON evidence) and exit",
    )
    args = parser.parse_args()

    if args.sales_pack:
        sales_pack_dir = Path(args.sales_pack)
        manifest = write_sales_pack(sales_pack_dir)
        print(f"✅ Pack de demo comercial guardado en {sales_pack_dir}")
        for scenario_id, meta in manifest.items():
            print(f"   - {scenario_id}: {meta['whatsapp_file']} ({meta['whatsapp_chars']} caracteres)")
        return

    save_dir = Path(args.save_dir) if args.save_dir else None

    if args.scenario:
        print_scenario(args.scenario, save_dir=save_dir)
    else:
        print()
        print("  🧠 Orvo Brain — Demo de Reportes Diarios")
        print("     Datos determinísticos, cero credenciales")
        print()

        for sid in SCENARIOS:
            print_scenario(sid, save_dir=save_dir)

    _divider()


if __name__ == "__main__":
    main()

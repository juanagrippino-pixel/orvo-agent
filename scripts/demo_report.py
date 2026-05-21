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
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brain.demo_scenarios import SCENARIOS, build_demo_report, build_demo_sales_brief
from app.brain.reporting import compose_daily_report_text, truncate_for_whatsapp


def _divider():
    print("=" * 60)


def format_sales_brief(scenario_id: str) -> str:
    """Return a concise seller talk track for one deterministic scenario."""
    brief = build_demo_sales_brief(scenario_id)
    lines = [
        "💼 Ficha comercial",
        f"- Negocio demo: {brief['business_name']}",
        f"- Dolor PyME: {brief['buyer_pain']}",
        f"- Ángulo de venta: {brief['sales_angle']}",
        f"- Pregunta para abrir: {brief['demo_prompt']}",
        f"- WhatsApp sample: {brief['whatsapp_chars']} caracteres / 1000",
        "- Alertas que ve el dueño:",
    ]
    if brief["top_alerts"]:
        lines.extend(f"  • {alert}" for alert in brief["top_alerts"])
    else:
        lines.append("  • Sin alertas: Orvo confirma que no hay urgencias.")

    lines.append("- Próximas acciones:")
    if brief["next_actions"]:
        lines.extend(f"  • {action}" for action in brief["next_actions"])
    else:
        lines.append("  • Mantener monitoreo diario y revisar tendencias por canal.")
    return "\n".join(lines)


def print_sales_brief(scenario_id: str) -> None:
    print()
    print(format_sales_brief(scenario_id))


def print_scenario(scenario_id: str, *, save_dir: Path | None = None, sales_brief: bool = False):
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

    if sales_brief:
        print_sales_brief(scenario_id)
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
        "--sales-brief",
        action="store_true",
        help="Print seller-facing pain, pitch angle and next actions for each scenario",
    )
    args = parser.parse_args()

    save_dir = Path(args.save_dir) if args.save_dir else None

    if args.scenario:
        print_scenario(args.scenario, save_dir=save_dir, sales_brief=args.sales_brief)
    else:
        print()
        print("  🧠 Orvo Brain — Demo de Reportes Diarios")
        print("     Datos determinísticos, cero credenciales")
        print()

        for sid in SCENARIOS:
            print_scenario(sid, save_dir=save_dir, sales_brief=args.sales_brief)

    _divider()


if __name__ == "__main__":
    main()

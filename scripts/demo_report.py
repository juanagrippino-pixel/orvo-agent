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

from app.brain.demo_scenarios import SCENARIOS, build_demo_report, format_demo_sales_summary
from app.brain.reporting import compose_daily_report_text, truncate_for_whatsapp


def _divider():
    print("=" * 60)


def print_scenario(scenario_id: str, *, save_dir: Path | None = None, sales_summary: bool = False):
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

    if sales_summary:
        print()
        print(format_demo_sales_summary(scenario_id))

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
        if sales_summary:
            (save_dir / f"{scenario_id}-sales.md").write_text(
                format_demo_sales_summary(scenario_id) + "\n",
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
        "--sales-summary",
        action="store_true",
        help="Print a compact prospect-facing talk track after each WhatsApp sample",
    )
    args = parser.parse_args()

    save_dir = Path(args.save_dir) if args.save_dir else None

    if args.scenario:
        print_scenario(args.scenario, save_dir=save_dir, sales_summary=args.sales_summary)
    else:
        print()
        print("  🧠 Orvo Brain — Demo de Reportes Diarios")
        print("     Datos determinísticos, cero credenciales")
        print()

        for sid in SCENARIOS:
            print_scenario(sid, save_dir=save_dir, sales_summary=args.sales_summary)

    _divider()


if __name__ == "__main__":
    main()

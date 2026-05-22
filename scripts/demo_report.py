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

from app.brain.demo_scenarios import SCENARIOS, build_demo_report
from app.brain.reporting import compose_daily_report_text, truncate_for_whatsapp


def _divider():
    print("=" * 60)


def build_whatsapp_sample(scenario_id: str) -> str:
    """Return the buyer-facing WhatsApp text for a demo scenario."""
    report = build_demo_report(scenario_id)
    return truncate_for_whatsapp(compose_daily_report_text(report))


def build_sales_pack_markdown() -> str:
    """Build a deterministic sales-pack README with copy/paste samples.

    The pack is intentionally credential-free: it gives a founder or seller a
    ready narrative for PyME prospects without needing to connect live stores.
    """
    lines = [
        "# Orvo Brain — Sales Demo Pack",
        "",
        (
            "Demo determinística para mostrarle a una PyME argentina/LatAm qué "
            "recibiría por WhatsApp sin pedir credenciales ni tocar sus sistemas."
        ),
        "",
        "## Cómo usarlo en una demo",
        "",
        "1. Abrí este README o compartí los archivos `*.whatsapp.txt`.",
        "2. Elegí el caso más parecido al prospecto: día normal, crisis de stock o multi-canal.",
        "3. Copiar y pegar el bloque de WhatsApp y explicar: métricas, alerta y acción sugerida.",
        "4. Cerrá con el valor: menos ventas perdidas, menos pauta desperdiciada y más control diario.",
        "",
        "## Mensajes listos para copiar",
    ]
    for scenario_id, scenario in SCENARIOS.items():
        sample = build_whatsapp_sample(scenario_id)
        lines.extend([
            "",
            f"### {scenario['title']}",
            "",
            scenario["description"],
            "",
            f"Archivo sugerido: `{scenario_id}.whatsapp.txt`",
            "",
            "```text",
            sample,
            "```",
        ])
    lines.extend([
        "",
        "## Objeciones frecuentes",
        "",
        "- **¿Inventan números?** No: cada métrica e insight sale con Fuentes verificables.",
        "- **¿Necesito integrar todo para verlo?** No: este pack es sembrado y sirve para validar valor antes de conectar datos reales.",
        "- **¿Qué se implementa primero?** Un reporte diario por WhatsApp con el conector que la PyME ya usa: CSV, Sheets, Tiendanube, MercadoLibre o Meta Ads.",
        "",
        "## Promesa comercial",
        "",
        "Orvo Brain no es otro tablero: resume cada mañana qué cambió, por qué importa y qué acción concreta tomar.",
        "",
    ])
    return "\n".join(lines)


def save_sales_pack(save_dir: Path) -> list[Path]:
    """Write sales-ready WhatsApp samples, JSON reports and README."""
    save_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    readme = save_dir / "README.md"
    readme.write_text(build_sales_pack_markdown(), encoding="utf-8")
    written.append(readme)
    for scenario_id in SCENARIOS:
        report = build_demo_report(scenario_id)
        sample = build_whatsapp_sample(scenario_id)
        sample_path = save_dir / f"{scenario_id}.whatsapp.txt"
        json_path = save_dir / f"{scenario_id}.report.json"
        sample_path.write_text(sample, encoding="utf-8")
        json_path.write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written.extend([sample_path, json_path])
    return written


def print_scenario(scenario_id: str, *, save_dir: Path | None = None):
    scenario = SCENARIOS[scenario_id]
    report = build_demo_report(scenario_id)
    text = compose_daily_report_text(report)
    text_truncated = build_whatsapp_sample(scenario_id)

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
        action="store_true",
        help="Write a buyer-ready sales pack (README + WhatsApp samples) to --save-dir",
    )
    args = parser.parse_args()

    save_dir = Path(args.save_dir) if args.save_dir else None

    if args.sales_pack:
        output_dir = save_dir or Path("examples/demo_sales_pack")
        written = save_sales_pack(output_dir)
        print(f"✅ Sales demo pack guardado en {output_dir}/")
        for path in written:
            print(f"- {path}")
        return

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

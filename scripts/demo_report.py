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


def _scenario_sales_angle(scenario_id: str) -> str:
    if scenario_id == "pyme-normal":
        return "Prueba confianza diaria: el dueño ve que todo está sano sin abrir planillas."
    if scenario_id == "pyme-stock-crisis":
        return "Prueba ROI urgente: evita quemar pauta cuando no hay stock ni respuesta comercial."
    if scenario_id == "pyme-multi-canal":
        return "Prueba control multi-canal: unifica Tiendanube, MercadoLibre y Meta Ads en un solo WhatsApp."
    return "Prueba operativa: convierte datos dispersos en acciones concretas para el dueño."


def build_sales_packet_markdown(scenario_ids: list[str]) -> str:
    """Build a concise README for saved demo assets.

    The packet is meant for sales calls: each scenario links the generated
    WhatsApp text and JSON payload, then explains the business value in plain
    PyME language without inventing metrics beyond the deterministic report.
    """
    lines = [
        "# Orvo Brain — Demo PyME sales packet",
        "",
        "Use este paquete para mostrarle a una PyME qué recibiría por WhatsApp: ",
        "datos determinísticos, evidencia por métrica y acciones operativas claras.",
        "",
        "## Cómo usarlo en una demo",
        "",
        "1. Abra el `.txt` del escenario y léalo como mensaje real de WhatsApp.",
        "2. Muestre el `.json` para probar que cada alerta sale de datos citados, no de humo.",
        "3. Cierre con la acción recomendada: qué haría hoy el dueño con ese aviso.",
    ]

    for scenario_id in scenario_ids:
        scenario = SCENARIOS[scenario_id]
        report = build_demo_report(scenario_id)
        text = truncate_for_whatsapp(compose_daily_report_text(report))
        severity_counts = {
            severity: sum(1 for insight in report.insights if insight.severity == severity)
            for severity in ("critical", "warning", "info")
        }
        actions = [insight.recommended_action for insight in report.insights[:3]]

        lines.extend([
            "",
            f"## {scenario['title']}",
            "",
            f"- Negocio demo: {report.business_name}",
            f"- Ángulo comercial: {_scenario_sales_angle(scenario_id)}",
            f"- Muestra WhatsApp: `{scenario_id}.txt` ({len(text)} caracteres)",
            f"- Payload auditable: `{scenario_id}.json`",
            (
                "- Alertas detectadas: "
                f"{severity_counts['critical']} críticas, "
                f"{severity_counts['warning']} warnings, "
                f"{severity_counts['info']} informativas"
            ),
            "- Acciones detectadas:",
        ])
        if actions:
            lines.extend(f"  - {action}" for action in actions)
        else:
            lines.append("  - Sin acción urgente; mantener seguimiento diario.")

    lines.extend([
        "",
        "## Comando reproducible",
        "",
        "```bash",
        "python scripts/demo_report.py --save-dir examples/demo_output",
        "```",
        "",
        "No requiere credenciales ni servicios externos.",
    ])
    return "\n".join(lines) + "\n"


def write_sales_packet(scenario_ids: list[str], save_dir: Path) -> None:
    save_dir.mkdir(parents=True, exist_ok=True)
    (save_dir / "README.md").write_text(
        build_sales_packet_markdown(scenario_ids),
        encoding="utf-8",
    )


def _divider():
    print("=" * 60)


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
    args = parser.parse_args()

    save_dir = Path(args.save_dir) if args.save_dir else None
    scenario_ids = [args.scenario] if args.scenario else list(SCENARIOS)

    if args.scenario:
        print_scenario(args.scenario, save_dir=save_dir)
    else:
        print()
        print("  🧠 Orvo Brain — Demo de Reportes Diarios")
        print("     Datos determinísticos, cero credenciales")
        print()

        for sid in SCENARIOS:
            print_scenario(sid, save_dir=save_dir)

    if save_dir:
        write_sales_packet(scenario_ids, save_dir)
        print(f"   🧾 Sales packet guardado en {save_dir / 'README.md'}")
        print()

    _divider()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Print deterministic Orvo Brain demo WhatsApp samples.

This CLI is intentionally network-free: it uses seeded PyME scenarios and the
same report composer as production so sales calls can show realistic, cited
WhatsApp output without setting up connectors or credentials.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brain.demo_scenarios import SCENARIOS, build_all_demo_reports, build_demo_report
from app.brain.reporting import compose_daily_report_text, truncate_for_whatsapp


def _print_scenario_list() -> None:
    print("Available Orvo Brain demo scenarios:")
    for scenario_id, scenario in SCENARIOS.items():
        print(f"- {scenario_id}: {scenario['title']}")
        print(f"  {scenario['description']}")


def _render_sample(scenario_id: str, *, max_chars: int) -> str:
    scenario = SCENARIOS[scenario_id]
    report = build_demo_report(scenario_id)
    text = truncate_for_whatsapp(
        compose_daily_report_text(report),
        max_chars=max_chars,
        preserve_sources_footer=True,
    )
    return "\n".join(
        [
            f"### {scenario_id} — {scenario['title']}",
            scenario["description"],
            "",
            f"WhatsApp sample ({len(text)}/{max_chars} chars):",
            "---",
            text,
            "---",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate copy/pasteable WhatsApp samples from seeded PyME demo scenarios."
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        help="Scenario to print. Omit to print every scenario.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available scenarios and exit.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=1000,
        help="Maximum WhatsApp body length per sample (default: 1000).",
    )
    args = parser.parse_args()

    if args.max_chars < 160:
        raise SystemExit("--max-chars must be at least 160 so the sample remains readable")

    if args.list:
        _print_scenario_list()
        return

    scenario_ids = [args.scenario] if args.scenario else [sid for sid, _ in build_all_demo_reports()]
    print("# Orvo Brain demo WhatsApp samples")
    print("Generated from deterministic seeded PyME scenarios; no external APIs or secrets used.")
    for index, scenario_id in enumerate(scenario_ids):
        if index:
            print()
        print(_render_sample(scenario_id, max_chars=args.max_chars))


if __name__ == "__main__":
    main()

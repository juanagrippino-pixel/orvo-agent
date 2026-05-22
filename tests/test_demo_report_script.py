"""Tests for the demo report CLI helpers used in sales demos."""

from pathlib import Path

from scripts.demo_report import build_sales_pack_markdown, save_sales_pack
from app.brain.demo_scenarios import SCENARIOS


def test_build_sales_pack_markdown_contains_buyer_ready_whatsapp_samples() -> None:
    markdown = build_sales_pack_markdown()

    assert "# Orvo Brain — Sales Demo Pack" in markdown
    assert "Cómo usarlo en una demo" in markdown
    assert "Copiar y pegar" in markdown
    for scenario in SCENARIOS.values():
        assert scenario["title"] in markdown
    assert "🧠 Orvo Brain" in markdown
    assert "Fuentes:" in markdown
    assert "API key" not in markdown
    assert "token" not in markdown.lower()


def test_save_sales_pack_writes_readme_and_whatsapp_samples(tmp_path: Path) -> None:
    written = save_sales_pack(tmp_path)

    assert tmp_path / "README.md" in written
    assert (tmp_path / "README.md").exists()
    for scenario_id in SCENARIOS:
        sample = tmp_path / f"{scenario_id}.whatsapp.txt"
        payload = tmp_path / f"{scenario_id}.report.json"
        assert sample in written
        assert payload in written
        assert sample.exists()
        assert payload.exists()
        sample_text = sample.read_text(encoding="utf-8")
        assert len(sample_text) <= 1000
        assert "🧠 Orvo Brain" in sample_text

from app.brain.demo_sales import build_demo_sales_onepager
from app.brain.demo_scenarios import SCENARIOS


def test_demo_sales_onepager_is_sellable_and_covers_all_scenarios():
    text = build_demo_sales_onepager()

    assert text.startswith("# Orvo Brain — demo comercial")
    assert "Para vender en 2 minutos" in text
    assert "WhatsApp" in text
    assert "ROI" in text
    for scenario_id, scenario in SCENARIOS.items():
        assert scenario_id in text
        assert scenario["title"] in text
    assert "[REDACTED]" not in text
    assert "token" not in text.lower()
    assert len(text) < 5000


def test_demo_sales_onepager_includes_proof_from_generated_reports():
    text = build_demo_sales_onepager()

    stock_row = next(line for line in text.splitlines() if "pyme-stock-crisis" in line)
    assert "Stock crítico" in stock_row
    assert "ARS" in text
    assert "caracteres" in text
    assert "python scripts/demo_report.py --sales-onepager" in text


def test_demo_report_cli_prints_sales_onepager():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/demo_report.py", "--sales-onepager"],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "# Orvo Brain — demo comercial" in result.stdout
    assert "pyme-multi-canal" in result.stdout
    assert "WhatsApp" in result.stdout

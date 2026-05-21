"""Tests for the one-command demo report scenarios."""

import subprocess
import sys
from pathlib import Path

from app.brain.demo_scenarios import (
    SCENARIOS,
    build_all_demo_reports,
    build_demo_report,
    build_demo_sales_brief,
)
from app.brain.reporting import compose_daily_report_text, truncate_for_whatsapp


def test_all_scenario_ids_exist():
    assert "pyme-normal" in SCENARIOS
    assert "pyme-stock-crisis" in SCENARIOS
    assert "pyme-multi-canal" in SCENARIOS


def test_each_scenario_has_required_keys():
    for sid, scenario in SCENARIOS.items():
        assert "title" in scenario, f"{sid} missing title"
        assert "description" in scenario, f"{sid} missing description"
        assert "payload" in scenario, f"{sid} missing payload"
        assert "business_name" in scenario["payload"]
        assert "metrics" in scenario["payload"]


def test_build_demo_report_returns_report():
    for sid in SCENARIOS:
        report = build_demo_report(sid)
        assert report.business_name
        assert report.metrics
        assert all(m.evidence for m in report.metrics)


def test_pyme_normal_no_critical_alerts():
    report = build_demo_report("pyme-normal")
    text = compose_daily_report_text(report)
    severities = [i.severity for i in report.insights]
    assert "critical" not in severities, "Normal day should not have critical alerts"


def test_pyme_stock_crisis_has_critical_alerts():
    report = build_demo_report("pyme-stock-crisis")
    text = compose_daily_report_text(report)
    severities = [i.severity for i in report.insights]
    assert "critical" in severities, "Stock crisis scenario must have a critical alert"
    assert "warning" in severities, "Stock crisis scenario should have warnings too"


def test_pyme_stock_crisis_text_content():
    report = build_demo_report("pyme-stock-crisis")
    text = compose_daily_report_text(report)
    assert "Stock crítico" in text or "stock bajo" in text.lower()
    assert "Café de Barrio" in text


def test_pyme_multi_canal_has_cross_channel_insights():
    report = build_demo_report("pyme-multi-canal")
    severities = [i.severity for i in report.insights]
    assert "info" in severities, "Multi-channel demo should show cross-channel info"
    revenue_tn = [m for m in report.metrics if m.key == "revenue_today_tn"]
    revenue_ml = [m for m in report.metrics if m.key == "revenue_today_ml"]
    assert revenue_tn, "Missing Tiendanube revenue metric"
    assert revenue_ml, "Missing MercadoLibre revenue metric"


def test_compose_daily_report_text_contains_business_name():
    for sid in SCENARIOS:
        report = build_demo_report(sid)
        text = compose_daily_report_text(report)
        assert report.business_name in text


def test_truncate_for_whatsapp_respects_budget():
    for sid in SCENARIOS:
        report = build_demo_report(sid)
        text = compose_daily_report_text(report)
        truncated = truncate_for_whatsapp(text, max_chars=1000)
        assert len(truncated) <= 1000


def test_build_all_demo_reports_returns_all():
    results = build_all_demo_reports()
    assert len(results) == len(SCENARIOS)
    for sid, report in results:
        assert sid in SCENARIOS
        assert report.business_name


def test_demo_scenario_metric_citations():
    """Every metric and insight in demo reports must carry evidence."""
    for sid in SCENARIOS:
        report = build_demo_report(sid)
        for metric in report.metrics:
            assert metric.evidence, f"{sid}: metric {metric.key} has no evidence"
        for insight in report.insights:
            assert insight.evidence, f"{sid}: insight {insight.title} has no evidence"


def test_demo_report_text_fits_whatsapp_for_scenarios():
    """All demo reports should either fit or be gracefully truncated."""
    for sid in SCENARIOS:
        report = build_demo_report(sid)
        text = compose_daily_report_text(report)
        truncated = truncate_for_whatsapp(text, max_chars=1000)
        # Truncated text should be under budget
        assert len(truncated) <= 1000
        # Should still contain the business name
        assert report.business_name in truncated


def test_each_scenario_has_sales_context():
    """Demo scenarios should include a concise seller talk track."""
    for sid, scenario in SCENARIOS.items():
        assert scenario.get("buyer_pain"), f"{sid} missing buyer_pain"
        assert scenario.get("sales_angle"), f"{sid} missing sales_angle"
        assert scenario.get("demo_prompt"), f"{sid} missing demo_prompt"


def test_demo_sales_brief_is_prospect_ready():
    brief = build_demo_sales_brief("pyme-stock-crisis")

    assert brief["scenario_id"] == "pyme-stock-crisis"
    assert brief["business_name"] == "Café de Barrio — Colegiales"
    assert brief["buyer_pain"]
    assert brief["sales_angle"]
    assert brief["demo_prompt"].endswith("?")
    assert brief["whatsapp_chars"] <= 1000
    assert len(brief["next_actions"]) <= 3
    assert any("stock" in alert.lower() for alert in brief["top_alerts"])
    assert any("paus" in action.lower() or "repos" in action.lower() for action in brief["next_actions"])


def test_demo_sales_brief_has_no_secret_like_values():
    forbidden = {"WHATSAPP_TOKEN", "ACCESS_TOKEN", "TIENDANUBE_ACCESS_TOKEN", "sk-"}
    for sid in SCENARIOS:
        brief_text = str(build_demo_sales_brief(sid))
        assert not any(value in brief_text for value in forbidden)


def test_demo_report_cli_can_print_sales_brief():
    script = Path(__file__).resolve().parents[1] / "scripts" / "demo_report.py"
    result = subprocess.run(
        [sys.executable, str(script), "--scenario", "pyme-stock-crisis", "--sales-brief"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Ficha comercial" in result.stdout
    assert "Dolor PyME" in result.stdout
    assert "Próximas acciones" in result.stdout
    assert "Café de Barrio" in result.stdout


def test_stock_crisis_demo_ads_section_uses_single_channel_revenue_for_roas():
    report = build_demo_report("pyme-stock-crisis")
    text = compose_daily_report_text(report)
    assert "ROAS estimado: 3.8x" in text

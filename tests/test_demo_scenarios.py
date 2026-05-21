"""Tests for the one-command demo report scenarios."""

from app.brain.demo_scenarios import SCENARIOS, build_all_demo_reports, build_demo_report
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


def test_whatsapp_truncation_preserves_sources_footer():
    report = build_demo_report("pyme-stock-crisis")
    text = compose_daily_report_text(report)
    truncated = truncate_for_whatsapp(
        text, max_chars=1000, preserve_sources_footer=True
    )

    assert len(truncated) <= 1000
    assert "... (ver reporte completo)" in truncated
    assert "🔗 Fuentes: Demo Tiendanube + Meta Ads" in truncated


def test_demo_cli_lists_scenarios():
    """Sales/demo operators can discover available demo stories from CLI."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/demo_orvo_brain_report.py", "--list"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "pyme-normal" in result.stdout
    assert "pyme-stock-crisis" in result.stdout
    assert "pyme-multi-canal" in result.stdout
    assert "Stock crítico" in result.stdout


def test_demo_cli_prints_whatsapp_sample_for_single_scenario():
    """One command should generate a bounded, copy/pasteable WhatsApp sample."""
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "scripts/demo_orvo_brain_report.py",
            "--scenario",
            "pyme-stock-crisis",
            "--max-chars",
            "1000",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "### pyme-stock-crisis" in result.stdout
    assert "WhatsApp sample" in result.stdout
    assert "Café de Barrio" in result.stdout
    assert "🧠 Orvo Brain" in result.stdout
    assert "🔗 Fuentes:" in result.stdout
    assert len(result.stdout) < 1800

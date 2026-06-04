from app.brain.adapters.sample import build_daily_report_from_payload


def test_build_daily_report_from_payload_generates_cited_report_and_insights():
    payload = {
        "business_name": "Artemea",
        "report_date": "2026-05-19",
        "source_label": "Sheet Artemea mayo",
        "metrics": {
            "revenue_today": 70000,
            "revenue_baseline": 100000,
            "stock_units": 3,
            "unanswered_conversations": 8,
        },
    }

    report = build_daily_report_from_payload(payload)

    assert report.business_name == "Artemea"
    assert len(report.metrics) == 4
    assert len(report.insights) == 3
    assert all(metric.evidence for metric in report.metrics)
    assert all(insight.evidence for insight in report.insights)


def test_build_daily_report_uses_defaults_for_minimal_payload():
    payload = {"business_name": "Tienda Test", "metrics": {"revenue_today": 1000}}

    report = build_daily_report_from_payload(payload)

    assert report.business_name == "Tienda Test"
    assert report.metrics[0].label == "Ventas de hoy"

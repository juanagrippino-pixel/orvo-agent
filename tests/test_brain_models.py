from datetime import date


def test_evidence_metric_insight_and_daily_report_models():
    from app.brain.models import DailyReport, Evidence, Insight, Metric

    source = Evidence(source="google_sheets", label="Ventas mayo")
    revenue = Metric(key="revenue_today", label="Ventas de hoy", value=120000, unit="ARS", evidence=[source])
    insight = Insight(
        severity="warning",
        title="Ventas debajo del promedio",
        explanation="Hoy vendiste menos que tu promedio reciente.",
        recommended_action="Revisar campañas y productos con caída.",
        evidence=[source],
    )

    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 19),
        metrics=[revenue],
        insights=[insight],
    )

    assert report.business_name == "Artemea"
    assert report.metrics[0].evidence[0].source == "google_sheets"
    assert report.insights[0].severity == "warning"


def test_insight_requires_evidence_to_prevent_uncited_claims():
    import pytest
    from pydantic import ValidationError
    from app.brain.models import Insight

    with pytest.raises(ValidationError):
        Insight(
            severity="critical",
            title="Stock crítico",
            explanation="Quedan pocas unidades.",
            recommended_action="Reponer stock.",
            evidence=[],
        )

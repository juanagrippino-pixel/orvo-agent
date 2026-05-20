from app.brain.models import Evidence, Metric


def evidence():
    return Evidence(source="google_sheets", label="Sheet ventas diaria")


def metric(key, value, unit=None):
    labels = {
        "revenue_today": "Ventas de hoy",
        "revenue_baseline": "Promedio reciente",
        "stock_units": "Stock disponible",
        "unanswered_conversations": "Conversaciones sin responder",
    }
    return Metric(key=key, label=labels[key], value=value, unit=unit, evidence=[evidence()])


def test_detects_revenue_drop_with_cited_evidence():
    from app.brain.insights import generate_insights

    insights = generate_insights([
        metric("revenue_today", 70000, "ARS"),
        metric("revenue_baseline", 100000, "ARS"),
    ])

    assert len(insights) == 1
    assert insights[0].severity == "warning"
    assert "Ventas" in insights[0].title
    assert insights[0].evidence[0].source == "google_sheets"


def test_ignores_small_revenue_changes():
    from app.brain.insights import generate_insights

    insights = generate_insights([
        metric("revenue_today", 92000, "ARS"),
        metric("revenue_baseline", 100000, "ARS"),
    ])

    assert insights == []


def test_detects_stock_risk():
    from app.brain.insights import generate_insights

    insights = generate_insights([metric("stock_units", 3, "units")])

    assert insights[0].severity == "critical"
    assert "stock" in insights[0].title.lower()
    assert insights[0].recommended_action


def test_detects_unanswered_conversations():
    from app.brain.insights import generate_insights

    insights = generate_insights([metric("unanswered_conversations", 9)])

    assert insights[0].severity == "warning"
    assert "mensajes" in insights[0].title.lower() or "conversaciones" in insights[0].title.lower()


def test_custom_thresholds_change_which_insight_fires():
    """Regression: passing an InsightThresholds object must shift which insights fire."""
    from app.brain.insights import generate_insights
    from app.brain.models import InsightThresholds

    metrics = [
        metric("revenue_today", 90000, "ARS"),
        metric("revenue_baseline", 100000, "ARS"),
    ]

    # Default threshold is 15% — a 10% drop must NOT fire a revenue-drop insight.
    assert generate_insights(metrics) == []

    # A stricter 5% threshold via InsightThresholds must fire the revenue-drop insight.
    strict = InsightThresholds(revenue_drop_threshold=0.05)
    insights = generate_insights(metrics, thresholds=strict)
    assert len(insights) == 1
    assert insights[0].severity == "warning"
    assert "ventas" in insights[0].title.lower()


def test_explicit_kwargs_override_thresholds_object():
    """Backwards compat: an explicit kwarg must override the thresholds-object value."""
    from app.brain.insights import generate_insights
    from app.brain.models import InsightThresholds

    metrics = [
        metric("revenue_today", 90000, "ARS"),
        metric("revenue_baseline", 100000, "ARS"),
    ]

    strict = InsightThresholds(revenue_drop_threshold=0.05)
    # kwarg 0.20 must win over the object's 0.05 → no insight at 10% drop.
    insights = generate_insights(metrics, thresholds=strict, revenue_drop_threshold=0.20)
    assert insights == []

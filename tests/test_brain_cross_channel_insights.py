"""Tests for cross-channel KPIs + attribution-lite insight rules."""

import pytest
from app.brain.models import Evidence, Metric
from app.brain.insights import generate_insights


def ev(source: str, label: str) -> Evidence:
    return Evidence(source=source, label=label)


def make_metric(key: str, value: float, unit: str | None = None, source: str = "tiendanube") -> Metric:
    labels = {
        "revenue_today_tn": "Ventas TN hoy",
        "revenue_today_ml": "Ventas ML hoy",
        "orders_today_tn": "Pedidos TN hoy",
        "orders_today_ml": "Pedidos ML hoy",
        "ad_spend_today": "Gasto en ads hoy",
        "stock_units": "Stock disponible",
        "total_revenue_today": "Revenue total hoy",
        # legacy keys used by existing tests
        "revenue_today": "Ventas de hoy",
        "revenue_baseline": "Promedio reciente",
        "unanswered_conversations": "Conversaciones sin responder",
    }
    return Metric(
        key=key,
        label=labels.get(key, key),
        value=value,
        unit=unit,
        evidence=[ev(source, labels.get(key, key))],
    )


# ── Rule 1: cross-channel revenue ─────────────────────────────────────────────

class TestCrossChannelRevenue:
    def test_emits_total_revenue_metric_and_info_insight(self):
        metrics = [
            make_metric("revenue_today_tn", 50_000, "ARS", "tiendanube"),
            make_metric("revenue_today_ml", 30_000, "ARS", "mercadolibre"),
        ]
        insights = generate_insights(metrics)
        # The combined-revenue insight is informational
        info = [i for i in insights if "total" in i.title.lower() or "canal" in i.title.lower()]
        assert len(info) >= 1
        assert info[0].severity == "info"
        # Evidence must cite both sources
        sources = {e.source for e in info[0].evidence}
        assert "tiendanube" in sources
        assert "mercadolibre" in sources

    def test_no_cross_channel_insight_without_ml(self):
        metrics = [make_metric("revenue_today_tn", 50_000, "ARS", "tiendanube")]
        insights = generate_insights(metrics)
        cross = [i for i in insights if "mercadolibre" in i.explanation.lower() or "ml" in i.title.lower()]
        assert cross == []


# ── Rule 2: channel mix ────────────────────────────────────────────────────────

class TestChannelMixInsight:
    def test_warns_when_ml_dominates_by_more_than_40pct(self):
        # ML = 60k, TN = 40k → ML/total = 60%, TN/total = 40%
        # ML > TN * 1.4 → 60k > 56k → True
        metrics = [
            make_metric("revenue_today_tn", 40_000, "ARS", "tiendanube"),
            make_metric("revenue_today_ml", 60_000, "ARS", "mercadolibre"),
        ]
        insights = generate_insights(metrics)
        mix_warn = [i for i in insights if "tiendanube" in i.explanation.lower() and i.severity == "warning"]
        assert len(mix_warn) >= 1
        assert mix_warn[0].evidence  # at least one evidence

    def test_no_channel_mix_warning_when_balanced(self):
        metrics = [
            make_metric("revenue_today_tn", 50_000, "ARS", "tiendanube"),
            make_metric("revenue_today_ml", 55_000, "ARS", "mercadolibre"),
        ]
        insights = generate_insights(metrics)
        mix_warn = [i for i in insights if "tiendanube" in i.explanation.lower() and i.severity == "warning"]
        assert mix_warn == []

    def test_no_channel_mix_warning_without_both_channels(self):
        # Only TN, no ML → can't compare
        metrics = [make_metric("revenue_today_tn", 10_000, "ARS", "tiendanube")]
        insights = generate_insights(metrics)
        mix_warn = [i for i in insights if "tiendanube" in i.explanation.lower() and i.severity == "warning"]
        assert mix_warn == []


# ── Rule 3: ROAS ───────────────────────────────────────────────────────────────

class TestROASInsight:
    def test_warns_when_roas_below_threshold(self):
        # spend=10k, revenue=20k → ROAS=2.0 < 3.0
        metrics = [
            make_metric("revenue_today_tn", 15_000, "ARS", "tiendanube"),
            make_metric("revenue_today_ml", 5_000, "ARS", "mercadolibre"),
            make_metric("ad_spend_today", 10_000, "ARS", "meta_ads"),
        ]
        insights = generate_insights(metrics)
        roas_warn = [i for i in insights if "roas" in i.title.lower() or "roas" in i.explanation.lower()]
        assert len(roas_warn) >= 1
        assert roas_warn[0].severity == "warning"

    def test_no_roas_warning_when_roas_acceptable(self):
        # spend=5k, revenue=30k → ROAS=6.0 >= 3.0
        metrics = [
            make_metric("revenue_today_tn", 20_000, "ARS", "tiendanube"),
            make_metric("revenue_today_ml", 10_000, "ARS", "mercadolibre"),
            make_metric("ad_spend_today", 5_000, "ARS", "meta_ads"),
        ]
        insights = generate_insights(metrics)
        roas_warn = [i for i in insights if "roas" in i.title.lower() or "roas" in i.explanation.lower()]
        assert roas_warn == []

    def test_no_roas_warning_when_zero_spend(self):
        metrics = [
            make_metric("revenue_today_tn", 50_000, "ARS", "tiendanube"),
            make_metric("ad_spend_today", 0, "ARS", "meta_ads"),
        ]
        insights = generate_insights(metrics)
        roas_warn = [i for i in insights if "roas" in i.title.lower() or "roas" in i.explanation.lower()]
        assert roas_warn == []

    def test_roas_configurable_threshold(self):
        # spend=10k, revenue=25k → ROAS=2.5; passes default 3.0 but fails threshold=2.0
        metrics = [
            make_metric("revenue_today_tn", 25_000, "ARS", "tiendanube"),
            make_metric("ad_spend_today", 10_000, "ARS", "meta_ads"),
        ]
        # With default threshold (3.0) → should warn
        insights_default = generate_insights(metrics)
        roas_warn_default = [i for i in insights_default if "roas" in i.title.lower() or "roas" in i.explanation.lower()]
        assert len(roas_warn_default) >= 1

        # With higher threshold (5.0) → still warns (2.5 < 5.0)
        insights_strict = generate_insights(metrics, roas_threshold=5.0)
        roas_warn_strict = [i for i in insights_strict if "roas" in i.title.lower() or "roas" in i.explanation.lower()]
        assert len(roas_warn_strict) >= 1

        # With lower threshold (2.0) → no warning (2.5 >= 2.0)
        insights_loose = generate_insights(metrics, roas_threshold=2.0)
        roas_warn_loose = [i for i in insights_loose if "roas" in i.title.lower() or "roas" in i.explanation.lower()]
        assert roas_warn_loose == []


# ── Rule 4: spend without sales ────────────────────────────────────────────────

class TestSpendWithoutSales:
    def test_critical_when_spend_positive_and_zero_orders(self):
        metrics = [
            make_metric("ad_spend_today", 5_000, "ARS", "meta_ads"),
            make_metric("orders_today_tn", 0, "units", "tiendanube"),
            make_metric("orders_today_ml", 0, "units", "mercadolibre"),
        ]
        insights = generate_insights(metrics)
        alert = [i for i in insights if "sin ventas" in i.title.lower() or "sin ventas" in i.explanation.lower()]
        assert len(alert) >= 1
        assert alert[0].severity == "critical"

    def test_no_alert_when_orders_exist(self):
        metrics = [
            make_metric("ad_spend_today", 5_000, "ARS", "meta_ads"),
            make_metric("orders_today_tn", 3, "units", "tiendanube"),
            make_metric("orders_today_ml", 0, "units", "mercadolibre"),
        ]
        insights = generate_insights(metrics)
        alert = [i for i in insights if "sin ventas" in i.title.lower() or "sin ventas" in i.explanation.lower()]
        assert alert == []

    def test_no_alert_when_zero_spend(self):
        metrics = [
            make_metric("ad_spend_today", 0, "ARS", "meta_ads"),
            make_metric("orders_today_tn", 0, "units", "tiendanube"),
        ]
        insights = generate_insights(metrics)
        alert = [i for i in insights if "sin ventas" in i.title.lower() or "sin ventas" in i.explanation.lower()]
        assert alert == []


# ── Rule 5: stock + ads collision ─────────────────────────────────────────────

class TestStockAdsCollision:
    def test_critical_when_low_stock_and_ads_active(self):
        metrics = [
            make_metric("stock_units", 3, "units", "tiendanube"),
            make_metric("ad_spend_today", 2_000, "ARS", "meta_ads"),
        ]
        insights = generate_insights(metrics)
        collision = [i for i in insights if "pausar" in i.title.lower() or "pausar" in i.recommended_action.lower()]
        assert len(collision) >= 1
        assert collision[0].severity == "critical"

    def test_no_collision_when_stock_ok(self):
        metrics = [
            make_metric("stock_units", 20, "units", "tiendanube"),
            make_metric("ad_spend_today", 2_000, "ARS", "meta_ads"),
        ]
        insights = generate_insights(metrics)
        collision = [i for i in insights if "pausar" in i.title.lower() or "pausar" in i.recommended_action.lower()]
        assert collision == []

    def test_no_collision_when_no_ads(self):
        metrics = [
            make_metric("stock_units", 2, "units", "tiendanube"),
            make_metric("ad_spend_today", 0, "ARS", "meta_ads"),
        ]
        insights = generate_insights(metrics)
        collision = [i for i in insights if "pausar" in i.title.lower() or "pausar" in i.recommended_action.lower()]
        assert collision == []


# ── Happy path (no insights) ───────────────────────────────────────────────────

class TestHappyPath:
    def test_no_insights_when_all_metrics_healthy(self):
        metrics = [
            make_metric("revenue_today_tn", 50_000, "ARS", "tiendanube"),
            make_metric("revenue_today_ml", 30_000, "ARS", "mercadolibre"),
            make_metric("orders_today_tn", 10, "units", "tiendanube"),
            make_metric("orders_today_ml", 5, "units", "mercadolibre"),
            make_metric("ad_spend_today", 5_000, "ARS", "meta_ads"),
            make_metric("stock_units", 50, "units", "tiendanube"),
        ]
        insights = generate_insights(metrics)
        # Only the informational cross-channel total should fire; no warnings/criticals
        problems = [i for i in insights if i.severity in ("warning", "critical")]
        assert problems == []

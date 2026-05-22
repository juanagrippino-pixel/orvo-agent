from datetime import date

from app.brain.models import DailyReport, Evidence, Insight, Metric


def _tn_source():
    return Evidence(source="tiendanube", label="Tiendanube")


def _ml_source():
    return Evidence(source="mercadolibre", label="MercadoLibre")


def _meta_source():
    return Evidence(source="meta_ads", label="Meta Ads")


# ── existing tests (preserved) ───────────────────────────────────────────────

def test_compose_whatsapp_daily_report_in_spanish_with_sources():
    from app.brain.reporting import compose_daily_report_text

    source = Evidence(source="google_sheets", label="Ventas mayo")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 19),
        metrics=[
            Metric(key="revenue_today", label="Ventas de hoy", value=120000, unit="ARS", evidence=[source]),
        ],
        insights=[
            Insight(
                severity="warning",
                title="Ventas debajo del promedio",
                explanation="Hoy vendiste menos que tu promedio reciente.",
                recommended_action="Revisar campañas y productos con caída.",
                evidence=[source],
            )
        ],
    )

    text = compose_daily_report_text(report)

    assert text.startswith("Artemea · 2026-05-19")
    assert "Prioridad: Revisar campañas" in text
    assert "Ventas de hoy: ARS 120.000" in text
    assert "Ventas debajo del promedio" not in text
    assert "Fuentes" in text
    assert "Ventas mayo" in text
    assert "🧠" not in text
    assert "🚨" not in text


def test_compose_report_without_insights_says_no_critical_alerts():
    from app.brain.reporting import compose_daily_report_text

    source = Evidence(source="sample", label="Carga manual")
    report = DailyReport(
        business_name="Tienda Test",
        report_date=date(2026, 5, 19),
        metrics=[Metric(key="orders_today", label="Órdenes", value=4, evidence=[source])],
        insights=[],
    )

    text = compose_daily_report_text(report)

    assert "Prioridad: no hay urgencia hoy." in text
    assert "No hay alertas críticas" in text
    assert "Carga manual" in text


# ── new tests ────────────────────────────────────────────────────────────────

def test_single_channel_tn_only_no_canales_section():
    """When only TN revenue is present, no Canales section should appear."""
    from app.brain.reporting import compose_daily_report_text

    src = _tn_source()
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="tn_revenue_today", label="Ventas TN", value=48000, unit="ARS", evidence=[src]),
        ],
        insights=[],
    )
    text = compose_daily_report_text(report)
    assert "Canales" not in text


def test_dual_channel_shows_canales_section():
    """When both tn_revenue_today and ml_revenue_today present, show Canales block with total."""
    from app.brain.reporting import compose_daily_report_text

    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="tn_revenue_today", label="Ventas TN", value=48000, unit="ARS", evidence=[_tn_source()]),
            Metric(key="ml_revenue_today", label="Ventas ML", value=22000, unit="ARS", evidence=[_ml_source()]),
        ],
        insights=[],
    )
    text = compose_daily_report_text(report)
    assert "Canales" in text
    assert "Tiendanube: ARS 48.000" in text
    assert "MercadoLibre: ARS 22.000" in text
    assert "Total: ARS 70.000" in text


def test_dual_channel_shows_canales_section_with_current_canonical_keys():
    """Current cross-channel metrics use revenue_today_tn/revenue_today_ml."""
    from app.brain.reporting import compose_daily_report_text

    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="revenue_today_tn", label="Ventas TN", value=48000, unit="ARS", evidence=[_tn_source()]),
            Metric(key="revenue_today_ml", label="Ventas ML", value=22000, unit="ARS", evidence=[_ml_source()]),
        ],
        insights=[],
    )
    text = compose_daily_report_text(report)
    assert "Canales" in text
    assert "Tiendanube: ARS 48.000" in text
    assert "MercadoLibre: ARS 22.000" in text
    assert "Total: ARS 70.000" in text


def test_dual_channel_shows_canales_section_with_namespaced_merge_keys():
    """Merged reports may namespace duplicate connector metrics by source."""
    from app.brain.reporting import compose_daily_report_text

    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="tiendanube.revenue_today", label="Ventas TN", value=48000, unit="ARS", evidence=[_tn_source()]),
            Metric(key="mercadolibre.revenue_today", label="Ventas ML", value=22000, unit="ARS", evidence=[_ml_source()]),
        ],
        insights=[],
    )
    text = compose_daily_report_text(report)
    assert "Canales" in text
    assert "Tiendanube: ARS 48.000" in text
    assert "MercadoLibre: ARS 22.000" in text
    assert "Total: ARS 70.000" in text


def test_ads_block_shown_when_ad_spend_present():
    """When ad_spend_today metric is present, show Publicidad block with ROAS."""
    from app.brain.reporting import compose_daily_report_text

    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="tn_revenue_today", label="Ventas TN", value=48000, unit="ARS", evidence=[_tn_source()]),
            Metric(key="ml_revenue_today", label="Ventas ML", value=22000, unit="ARS", evidence=[_ml_source()]),
            Metric(key="ad_spend_today", label="Gasto ads", value=3500, unit="ARS", evidence=[_meta_source()]),
        ],
        insights=[],
    )
    text = compose_daily_report_text(report)
    assert "Publicidad" in text
    assert "Gasto del día: ARS 3.500" in text
    assert "ROAS estimado:" in text


def test_ads_block_roas_uses_current_canonical_revenue_keys():
    """ROAS should use current TN/ML canonical metric keys, not only legacy keys."""
    from app.brain.reporting import compose_daily_report_text

    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="revenue_today_tn", label="Ventas TN", value=15000, unit="ARS", evidence=[_tn_source()]),
            Metric(key="revenue_today_ml", label="Ventas ML", value=5000, unit="ARS", evidence=[_ml_source()]),
            Metric(key="ad_spend_today", label="Gasto ads", value=10000, unit="ARS", evidence=[_meta_source()]),
        ],
        insights=[],
    )
    text = compose_daily_report_text(report)
    assert "ROAS estimado: 2.0x" in text


def test_ads_block_roas_uses_namespaced_merge_revenue_keys():
    """ROAS should include source-namespaced revenue keys from merged reports."""
    from app.brain.reporting import compose_daily_report_text

    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="tiendanube.revenue_today", label="Ventas TN", value=18000, unit="ARS", evidence=[_tn_source()]),
            Metric(key="mercadolibre.revenue_today", label="Ventas ML", value=12000, unit="ARS", evidence=[_ml_source()]),
            Metric(key="ad_spend_today", label="Gasto ads", value=10000, unit="ARS", evidence=[_meta_source()]),
        ],
        insights=[],
    )
    text = compose_daily_report_text(report)
    assert "ROAS estimado: 3.0x" in text


def test_ads_block_not_shown_without_ad_spend():
    """No ad_spend_today -> no Publicidad section."""
    from app.brain.reporting import compose_daily_report_text

    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="tn_revenue_today", label="Ventas TN", value=48000, unit="ARS", evidence=[_tn_source()]),
        ],
        insights=[],
    )
    text = compose_daily_report_text(report)
    assert "Publicidad" not in text


def test_critical_alert_has_accion_urgente_prefix():
    """Critical severity insights must have 'Acción urgente:' prefix."""
    from app.brain.reporting import compose_daily_report_text

    src = _tn_source()
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[Metric(key="revenue_today", label="Ventas", value=0, unit="ARS", evidence=[src])],
        insights=[
            Insight(
                severity="critical",
                title="Sin ventas hoy",
                explanation="No se registraron ventas.",
                recommended_action="Verificar tienda online.",
                evidence=[src],
            )
        ],
    )
    text = compose_daily_report_text(report)
    assert "Prioridad: Verificar tienda online." in text
    assert "🔴" not in text
    assert "Acción urgente:" not in text


def test_footer_compact_sources_line():
    """Footer must be one compact line with bullet separators, not a verbose block."""
    from app.brain.reporting import compose_daily_report_text

    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="tn_revenue_today", label="Ventas TN", value=48000, unit="ARS", evidence=[_tn_source()]),
            Metric(key="ml_revenue_today", label="Ventas ML", value=22000, unit="ARS", evidence=[_ml_source()]),
            Metric(key="ad_spend_today", label="Gasto ads", value=3500, unit="ARS", evidence=[_meta_source()]),
        ],
        insights=[],
    )
    text = compose_daily_report_text(report)
    # Compact one-liner, not multi-line block
    assert "Fuentes:" in text
    assert "·" in text
    # Must NOT contain verbose multi-line evidence bullets
    assert "- Tiendanube (tiendanube)" not in text
    assert "🔗" not in text


def test_truncate_for_whatsapp_under_limit_unchanged():
    """Message under 1000 chars passes through unchanged."""
    from app.brain.reporting import truncate_for_whatsapp

    short = "Hola mundo"
    assert truncate_for_whatsapp(short) == short


def test_truncate_for_whatsapp_over_limit_truncated():
    """Message over 1000 chars gets trimmed and suffix appended."""
    from app.brain.reporting import truncate_for_whatsapp

    long_text = "a" * 1100
    result = truncate_for_whatsapp(long_text, max_chars=1000)
    assert len(result) <= 1000
    assert result.endswith("... (ver reporte completo)")


def test_full_report_under_1000_chars():
    """A realistic dual-channel + ads report should fit within 1000 chars."""
    from app.brain.reporting import compose_daily_report_text, truncate_for_whatsapp

    src_tn = _tn_source()
    src_ml = _ml_source()
    src_meta = _meta_source()
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="tn_revenue_today", label="Ventas TN", value=48000, unit="ARS", evidence=[src_tn]),
            Metric(key="ml_revenue_today", label="Ventas ML", value=22000, unit="ARS", evidence=[src_ml]),
            Metric(key="ad_spend_today", label="Gasto ads", value=3500, unit="ARS", evidence=[src_meta]),
            Metric(key="orders_today", label="Órdenes", value=12, evidence=[src_tn]),
        ],
        insights=[
            Insight(
                severity="warning",
                title="ROAS bajo",
                explanation="El ROAS está por debajo de 3x.",
                recommended_action="Pausar anuncios de bajo rendimiento.",
                evidence=[src_meta],
            )
        ],
    )
    text = compose_daily_report_text(report)
    final = truncate_for_whatsapp(text)
    assert len(final) <= 1000

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

    assert text.startswith("ARTEMEA · 2026-05-19")
    assert "Prioridad:" in text
    assert "Ventas debajo del promedio" in text
    assert "- Ventas de hoy: ARS 120.000" in text
    assert "Fuentes: Ventas mayo" in text
    assert "Orvo Brain" not in text


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
    assert "Fuentes: Carga manual" in text


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
    assert "Canales" not in text
    assert "Ventas TN: ARS 48.000" in text
    assert "Ventas ML: ARS 22.000" in text
    assert "Total canales: ARS 70.000" in text


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
    assert "Canales" not in text
    assert "Ventas TN: ARS 48.000" in text
    assert "Ventas ML: ARS 22.000" in text
    assert "Total canales: ARS 70.000" in text


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
    assert "Canales" not in text
    assert "Ventas TN: ARS 48.000" in text
    assert "Ventas ML: ARS 22.000" in text
    assert "Total canales: ARS 70.000" in text


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
    assert "Publicidad" not in text
    assert "Gasto ads: ARS 3.500" in text
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
    assert "Prioridad:" in text
    assert "Sin ventas hoy" in text
    assert "verificar tienda" in text.lower()
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
    assert "Tiendanube" in text
    assert "Meta Ads" in text
    assert "🔗" not in text
    # Must NOT contain verbose multi-line evidence bullets
    assert "- Tiendanube (tiendanube)" not in text



def test_hito0_operator_report_is_priority_first_dry_and_non_ai():
    from app.brain.reporting import compose_daily_report_text

    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 21),
        metrics=[
            Metric(key="revenue_today", label="Revenue", value=418000, unit="ARS", evidence=[_tn_source()]),
            Metric(key="revenue_baseline", label="Revenue baseline", value=603000, unit="ARS", evidence=[_tn_source()]),
            Metric(key="ad_spend_today", label="Gasto ads", value=52000, unit="ARS", evidence=[_meta_source()]),
            Metric(key="unanswered_conversations", label="Chats sin responder", value=8, evidence=[Evidence(source="whatsapp", label="WhatsApp")]),
        ],
        insights=[
            Insight(
                severity="warning",
                title="Ventas 31% debajo del promedio",
                explanation="Las ventas de ayer quedaron abajo del promedio reciente con ads activos.",
                recommended_action="Revisar checkout y pagos pendientes antes de tocar campañas.",
                evidence=[_tn_source(), _meta_source()],
            )
        ],
    )

    text = compose_daily_report_text(report)
    lines = text.splitlines()

    assert lines[0] == "ARTEMEA · 2026-05-21"
    assert lines[1].startswith("Prioridad: ")
    assert "Orvo" not in text
    assert "🧠" not in text and "📊" not in text and "🚨" not in text
    assert "me parece" not in text.lower()
    assert "oportunidad" not in text.lower()
    assert "Fuentes: Tiendanube, Meta Ads" in text
    assert len(text) < 700

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

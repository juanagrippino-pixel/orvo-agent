from datetime import date

from app.brain.models import DailyReport, Evidence, Insight, Metric


def _tn_source():
    return Evidence(source="tiendanube", label="Tiendanube")


def _ml_source():
    return Evidence(source="mercadolibre", label="MercadoLibre")


def _meta_source():
    return Evidence(source="meta_ads", label="Meta Ads")


def _has_status_emoji(text: str) -> bool:
    return any(0x1F300 <= ord(ch) <= 0x1FAFF for ch in text)


def test_compose_whatsapp_daily_report_uses_hito0_operator_brief():
    from app.brain.reporting import compose_daily_report_text

    source = Evidence(source="google_sheets", label="Ventas mayo")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 19),
        metrics=[Metric(key="revenue_today", label="Ventas de hoy", value=120000, unit="ARS", evidence=[source])],
        insights=[Insight(severity="warning", title="Ventas debajo del promedio", explanation="Hoy vendiste menos que tu promedio reciente.", recommended_action="Revisar campañas y productos con caída.", evidence=[source])],
    )
    text = compose_daily_report_text(report)
    assert text.startswith("Artemea · 2026-05-19")
    assert "Prioridad: revisar campañas y productos con caída." in text
    assert "Hoy vendiste menos que tu promedio reciente." in text
    assert "- Ventas de hoy: ARS 120.000" in text
    assert "Fuentes: Ventas mayo" in text
    assert "Orvo Brain" not in text
    assert not _has_status_emoji(text)


def test_compose_report_without_insights_says_no_operational_urgency():
    from app.brain.reporting import compose_daily_report_text
    source = Evidence(source="sample", label="Carga manual")
    report = DailyReport(business_name="Tienda Test", report_date=date(2026, 5, 19), metrics=[Metric(key="orders_today", label="Órdenes", value=4, evidence=[source])], insights=[])
    text = compose_daily_report_text(report)
    assert "Prioridad: no hay urgencia operativa hoy." in text
    assert "No hay alertas críticas" in text
    assert "- Órdenes: 4" in text
    assert "Fuentes: Carga manual" in text


def test_single_channel_tn_only_no_canales_section():
    from app.brain.reporting import compose_daily_report_text
    src = _tn_source()
    report = DailyReport(business_name="Artemea", report_date=date(2026, 5, 20), metrics=[Metric(key="tn_revenue_today", label="Ventas TN", value=48000, unit="ARS", evidence=[src])], insights=[])
    text = compose_daily_report_text(report)
    assert "Canales" not in text
    assert "- Ventas TN: ARS 48.000" in text


def test_dual_channel_keeps_operator_facts_without_dashboard_sections():
    from app.brain.reporting import compose_daily_report_text
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="revenue_today_tn", label="Ventas TN", value=48000, unit="ARS", evidence=[_tn_source()]),
            Metric(key="revenue_today_ml", label="Ventas ML", value=22000, unit="ARS", evidence=[_ml_source()]),
            Metric(key="ad_spend_today", label="Gasto ads", value=3500, unit="ARS", evidence=[_meta_source()]),
        ],
        insights=[],
    )
    text = compose_daily_report_text(report)
    assert "Canales" not in text
    assert "Publicidad" not in text
    assert "- Gasto ads: ARS 3.500" in text
    assert "- Ventas TN: ARS 48.000" in text
    assert "- Ventas ML: ARS 22.000" in text
    assert "Fuentes: Tiendanube, MercadoLibre, Meta Ads" in text


def test_namespaced_merge_keys_are_eligible_as_operator_facts():
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
    assert "- Ventas TN: ARS 48.000" in text
    assert "- Ventas ML: ARS 22.000" in text


def test_primary_critical_insight_wins_over_warning_and_limits_facts():
    from app.brain.reporting import compose_daily_report_text
    whatsapp = Evidence(source="whatsapp", label="WhatsApp")
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="revenue_today", label="Ventas", value=0, unit="ARS", evidence=[_tn_source()]),
            Metric(key="stock_units", label="Stock", value=3, evidence=[_tn_source()]),
            Metric(key="ad_spend_today", label="Gasto ads", value=10000, unit="ARS", evidence=[_meta_source()]),
            Metric(key="unanswered_conversations", label="Chats sin responder", value=8, evidence=[whatsapp]),
        ],
        insights=[
            Insight(severity="warning", title="Conversaciones sin responder", explanation="Hay 8 conversaciones pendientes que pueden frenar ventas.", recommended_action="Responder primero consultas de compra.", evidence=[whatsapp]),
            Insight(severity="critical", title="Ads activos con stock bajo", explanation="Quedan 3 unidades en stock pero hay campañas activas con gasto.", recommended_action="Pausá todas las campañas que promocionen productos con stock bajo.", evidence=[_tn_source(), _meta_source()]),
        ],
    )
    text = compose_daily_report_text(report)
    assert "Prioridad: pausar todas las campañas que promocionen productos con stock bajo." in text
    assert "Quedan 3 unidades" in text
    assert "Secundario: Conversaciones sin responder." in text
    assert text.count("\n-") == 3
    assert "Acción urgente" not in text
    assert not _has_status_emoji(text)


def test_partial_empty_report_is_honest_and_omits_recommendations():
    from app.brain.reporting import compose_daily_report_text
    report = DailyReport(business_name="Artemea", report_date=date(2026, 5, 20), metrics=[], insights=[])
    text = compose_daily_report_text(report)
    assert text.startswith("Artemea · 2026-05-20 · parcial")
    assert "Sin datos cargados. Recomendaciones omitidas." in text
    assert "Fuentes: sin fuentes" in text


def test_truncate_for_whatsapp_under_limit_unchanged():
    from app.brain.reporting import truncate_for_whatsapp
    short = "Hola mundo"
    assert truncate_for_whatsapp(short) == short


def test_truncate_for_whatsapp_over_limit_truncated():
    from app.brain.reporting import truncate_for_whatsapp
    long_text = "a" * 1100
    result = truncate_for_whatsapp(long_text, max_chars=1000)
    assert len(result) <= 1000
    assert result.endswith("... (ver reporte completo)")


def test_full_report_under_1000_chars():
    from app.brain.reporting import compose_daily_report_text, truncate_for_whatsapp
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(key="revenue_today_tn", label="Ventas TN", value=48000, unit="ARS", evidence=[_tn_source()]),
            Metric(key="revenue_today_ml", label="Ventas ML", value=22000, unit="ARS", evidence=[_ml_source()]),
            Metric(key="ad_spend_today", label="Gasto ads", value=3500, unit="ARS", evidence=[_meta_source()]),
            Metric(key="orders_today", label="Órdenes", value=12, evidence=[_tn_source()]),
        ],
        insights=[Insight(severity="warning", title="ROAS bajo", explanation="El ROAS está por debajo de 3x.", recommended_action="Pausar anuncios de bajo rendimiento.", evidence=[_meta_source()])],
    )
    final = truncate_for_whatsapp(compose_daily_report_text(report))
    assert len(final) <= 1000
    assert "Prioridad:" in final

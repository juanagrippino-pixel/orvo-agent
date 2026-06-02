from datetime import date, datetime, timezone

from app.brain.models import DailyReport, Evidence, Insight, Metric
from app.brain.operational_cases import (
    OperationalCase,
    OperationalCaseEvidenceMetric,
    OperationalCaseEvidenceSnapshot,
    OperationalCaseTimelineEvent,
)


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

    assert "Orvo Brain" in text
    assert "Artemea" in text
    assert "Ventas de hoy: ARS 120.000" in text
    assert "Ventas debajo del promedio" in text
    assert "Revisar campañas" in text
    assert "Fuentes" in text
    assert "Ventas mayo" in text


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

    assert "Sin alertas críticas" in text
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
    assert "🔴" in text
    assert "Acción urgente:" in text


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
    assert "🔗 Fuentes:" in text
    assert "·" in text
    # Must NOT contain verbose multi-line evidence bullets
    assert "- Tiendanube (tiendanube)" not in text


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


def test_alerts_sorted_by_severity_critical_first():
    """Alertas section must render critical → warning → info regardless of insertion order."""
    from app.brain.reporting import compose_daily_report_text

    src = _tn_source()
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[Metric(key="revenue_today", label="Ventas", value=50000, unit="ARS", evidence=[src])],
        insights=[
            Insight(
                severity="info",
                title="Info menor",
                explanation="Dato informativo.",
                recommended_action="Sin acción requerida.",
                evidence=[src],
            ),
            Insight(
                severity="critical",
                title="Sin ventas hoy",
                explanation="No se registraron ventas.",
                recommended_action="Verificar tienda.",
                evidence=[src],
            ),
            Insight(
                severity="warning",
                title="ROAS bajo",
                explanation="El ROAS está por debajo de 3x.",
                recommended_action="Pausar anuncios.",
                evidence=[src],
            ),
        ],
    )
    text = compose_daily_report_text(report)
    pos_critical = text.index("Sin ventas hoy")
    pos_warning = text.index("ROAS bajo")
    pos_info = text.index("Info menor")
    assert pos_critical < pos_warning < pos_info


def test_compose_daily_report_redacts_inline_secrets_from_labels_and_insights():
    """Daily WhatsApp reports are dispatched artifacts and must be redacted at the
    composition boundary, mirroring compose_owner_case_brief.

    Reason: if an upstream connector or insight builder accidentally bakes a
    bearer/access_token into a metric label, insight title, action, or evidence
    label, the daily WhatsApp dispatch (which only truncates) would leak the raw
    value to the owner's phone.
    """
    from app.brain.reporting import compose_daily_report_text

    leaky_source = Evidence(
        source="tiendanube",
        label="Tiendanube access_token=raw_label_secret_1",
    )
    report = DailyReport(
        business_name="Artemea",
        report_date=date(2026, 5, 20),
        metrics=[
            Metric(
                key="revenue_today",
                label="Ventas access_token=raw_metric_secret_2",
                value=12000,
                unit="ARS",
                evidence=[leaky_source],
            ),
        ],
        insights=[
            Insight(
                severity="warning",
                title="ROAS bajo Bearer raw_insight_secret_3",
                explanation="ROAS por debajo Bearer raw_insight_secret_4.",
                recommended_action="Revisar Bearer raw_insight_secret_5.",
                evidence=[leaky_source],
            )
        ],
    )

    text = compose_daily_report_text(report)

    assert "raw_label_secret_1" not in text
    assert "raw_metric_secret_2" not in text
    assert "raw_insight_secret_3" not in text
    assert "raw_insight_secret_4" not in text
    assert "raw_insight_secret_5" not in text
    # Structural surroundings should still survive redaction.
    assert "Orvo Brain — Artemea" in text
    assert "ROAS bajo" in text


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


def _utc(hour: int = 8) -> datetime:
    return datetime(2026, 5, 24, hour, tzinfo=timezone.utc)


def _owner_case(
    *,
    case_id: str,
    title: str,
    case_type: str = "stockout_risk",
    severity: str = "warning",
    priority_score: int = 70,
    status: str = "open",
    source: str = "tiendanube",
    source_label: str = "Tiendanube",
    freshness_state: str = "fresh",
    metric_value: int = 3,
    recommended_action: str = "Reponer stock o pausar campañas.",
    token: str = "raw_case_brief_secret",
    opened_at: datetime | None = None,
    timeline: list[OperationalCaseTimelineEvent] | None = None,
) -> OperationalCase:
    kwargs = {"resolved_at": _utc(10)} if status == "resolved" else {}
    opened = opened_at if opened_at is not None else _utc(8)
    updated = max(opened, _utc(9))
    return OperationalCase(
        **kwargs,
        case_id=case_id,
        business_id="artemea",
        case_type=case_type,  # type: ignore[arg-type]
        dedupe_key=f"artemea/stockout/{case_id}",
        title=f"{title} access_token={token}",
        status=status,
        severity=severity,  # type: ignore[arg-type]
        priority_score=priority_score,
        entity_scope={"kind": "product", "id": "sku-1", "label": "Remera Negra"},
        opened_at=opened,
        updated_at=updated,
        timeline=timeline or [],
        latest_run_id="run-1",
        evidence_refs=[f"evidence://tiendanube/stock?access_token={token}"],
        artifact_refs=[f"ledger://runs/run-1/daily-report?access_token={token}"],
        evidence_snapshots=[
            OperationalCaseEvidenceSnapshot(
                snapshot_key=f"run-1/evidence://tiendanube/stock/{case_id}?access_token={token}",
                captured_at=_utc(8),
                run_id="run-1",
                artifact_ref=f"ledger://runs/run-1/daily-report?access_token={token}",
                evidence_ref=f"evidence://tiendanube/stock/{case_id}?access_token={token}",
                source=source,
                source_label=source_label,
                case_type=case_type,  # type: ignore[arg-type]
                entity_scope={"kind": "product", "id": "sku-1", "label": "Remera Negra"},
                summary=f"Quedan pocas unidades Bearer {token}",
                freshness_state=freshness_state,  # type: ignore[arg-type]
                metrics=[
                    OperationalCaseEvidenceMetric(
                        metric_key="commerce.inventory.available_units",
                        label="Stock disponible",
                        value=metric_value,
                        unit="units",
                        observed_at=_utc(8),
                    )
                ],
            )
        ],
        metadata={"recommended_action": recommended_action, "access_token": token},
    )


def test_compose_owner_case_brief_prioritizes_open_cases_with_evidence_and_actions():
    from app.brain.reporting import compose_owner_case_brief

    low = _owner_case(case_id="case-low", title="ROAS bajo", severity="warning", priority_score=60)
    high = _owner_case(case_id="case-high", title="Stock crítico", severity="critical", priority_score=95, metric_value=2)
    resolved = _owner_case(case_id="case-done", title="Resuelto", status="resolved", priority_score=100)

    text = compose_owner_case_brief("Artemea", [low, high, resolved], report_date=date(2026, 5, 24))

    assert "🧠 Orvo — Artemea" in text
    assert "2 temas operativos" in text
    assert text.index("Stock crítico") < text.index("ROAS bajo")
    assert "case-high" in text
    assert "Tiendanube" in text
    assert "Stock disponible: 2 units" in text
    assert "Reponer stock o pausar campañas." in text
    assert "Resuelto" not in text
    assert "raw_case_brief_secret" not in text


def test_compose_owner_case_brief_excludes_internal_case_families_from_owner_surface():
    from app.brain.reporting import compose_owner_case_brief

    visible = _owner_case(case_id="case-visible", title="Stock crítico", priority_score=90)
    internal = _owner_case(
        case_id="case-internal",
        title="Mix de canales interno",
        case_type="channel_mix_shift",
        priority_score=100,
    )

    text = compose_owner_case_brief("Artemea", [internal, visible], report_date=date(2026, 5, 24))

    assert "1 tema operativo" in text
    assert "Stock crítico" in text
    assert "case-visible" in text
    assert "Mix de canales interno" not in text
    assert "case-internal" not in text


def test_compose_owner_case_brief_marks_degraded_evidence():
    from app.brain.reporting import compose_owner_case_brief

    case = _owner_case(
        case_id="case-stale",
        title="Datos desactualizados",
        freshness_state="stale",
        source="google_sheets",
        source_label="Sheet ventas",
    )

    text = compose_owner_case_brief("Artemea", [case], report_date=date(2026, 5, 24))

    assert "Evidencia degradada" in text
    assert "Sheet ventas" in text


def test_compose_owner_case_brief_empty_queue_is_reassuring():
    from app.brain.reporting import compose_owner_case_brief

    text = compose_owner_case_brief("Artemea", [], report_date=date(2026, 5, 24))

    assert "sin temas operativos abiertos" in text.lower()
    assert len(text) < 500


def test_compose_owner_case_brief_distinguishes_total_open_from_display_limit():
    from app.brain.reporting import compose_owner_case_brief

    cases = [
        _owner_case(case_id=f"case-{index}", title=f"Tema {index}", priority_score=90 - index)
        for index in range(5)
    ]

    text = compose_owner_case_brief("Artemea", cases, report_date=date(2026, 5, 24), max_cases=3)

    assert "Hay 5 temas operativos abiertos" in text
    assert "te muestro los 3 principales" in text
    assert "Tema 0" in text
    assert "Tema 2" in text
    assert "Tema 3" not in text


def test_owner_brief_marks_new_today_when_opened_on_report_date():
    from app.brain.reporting import compose_owner_case_brief

    case = _owner_case(
        case_id="case-new",
        title="Sin ventas",
        opened_at=datetime(2026, 5, 24, 8, tzinfo=timezone.utc),
    )

    text = compose_owner_case_brief("Artemea", [case], report_date=date(2026, 5, 24))

    assert "Nuevo hoy" in text
    assert "Abierto hace" not in text


def test_owner_brief_shows_age_for_cases_opened_before_report_date():
    from app.brain.reporting import compose_owner_case_brief

    case = _owner_case(
        case_id="case-old",
        title="Sin ventas",
        opened_at=datetime(2026, 5, 22, 8, tzinfo=timezone.utc),
    )

    text = compose_owner_case_brief("Artemea", [case], report_date=date(2026, 5, 24))

    assert "Abierto hace 2 días" in text
    assert "Nuevo hoy" not in text


def test_owner_brief_uses_latest_reopen_event_for_age():
    from app.brain.reporting import compose_owner_case_brief

    case = _owner_case(
        case_id="case-reopened-today",
        title="Stock crítico",
        opened_at=datetime(2026, 5, 10, 8, tzinfo=timezone.utc),
        timeline=[
            OperationalCaseTimelineEvent(
                event_type="case_reopened",
                summary="Reabierto por nueva detección",
                created_at=datetime(2026, 5, 24, 7, tzinfo=timezone.utc),
            ),
        ],
    )

    text = compose_owner_case_brief("Artemea", [case], report_date=date(2026, 5, 24))

    assert "Reabierto hoy" in text
    assert "Abierto hace" not in text
    assert "Nuevo hoy" not in text


def test_owner_brief_shows_reopened_age_for_past_reopen():
    from app.brain.reporting import compose_owner_case_brief

    case = _owner_case(
        case_id="case-reopened-old",
        title="Stock crítico",
        opened_at=datetime(2026, 5, 1, 8, tzinfo=timezone.utc),
        timeline=[
            OperationalCaseTimelineEvent(
                event_type="case_reopened",
                summary="Reapertura previa",
                created_at=datetime(2026, 5, 19, 7, tzinfo=timezone.utc),
            ),
            OperationalCaseTimelineEvent(
                event_type="case_reopened",
                summary="Última reapertura",
                created_at=datetime(2026, 5, 21, 7, tzinfo=timezone.utc),
            ),
        ],
    )

    text = compose_owner_case_brief("Artemea", [case], report_date=date(2026, 5, 24))

    assert "Reabierto hace 3 días" in text
    assert "Reabierto hace 5 días" not in text


def test_owner_brief_marks_acknowledged_status_with_seen_marker():
    from app.brain.reporting import compose_owner_case_brief

    ack = _owner_case(
        case_id="case-ack",
        title="Stock bajo",
        status="acknowledged",
    )
    open_case = _owner_case(
        case_id="case-open",
        title="ROAS bajo",
        status="open",
    )

    text = compose_owner_case_brief(
        "Artemea", [ack, open_case], report_date=date(2026, 5, 24)
    )

    # acknowledged case carries seen marker
    ack_pos = text.index("case-ack")
    open_pos = text.index("case-open")
    next_caso = text.find("   Caso:", ack_pos + 1)
    ack_block = text[ack_pos: next_caso if next_caso != -1 else len(text)]
    open_block = text[open_pos:]
    assert "✓ Visto" in ack_block
    assert "✓ Visto" not in open_block


def test_owner_brief_fits_whatsapp_budget_with_age_and_status_lines():
    from app.brain.reporting import compose_owner_case_brief, truncate_for_whatsapp

    cases = [
        _owner_case(
            case_id="case-critical-reopened",
            title="Stock crítico recurrente",
            severity="critical",
            priority_score=95,
            opened_at=datetime(2026, 5, 1, 8, tzinfo=timezone.utc),
            timeline=[
                OperationalCaseTimelineEvent(
                    event_type="case_reopened",
                    summary="Recurrencia detectada",
                    created_at=datetime(2026, 5, 22, 8, tzinfo=timezone.utc),
                )
            ],
        ),
        _owner_case(
            case_id="case-ack-stale",
            title="ROAS bajo",
            severity="warning",
            priority_score=80,
            status="acknowledged",
            opened_at=datetime(2026, 5, 20, 8, tzinfo=timezone.utc),
            freshness_state="stale",
            source="google_sheets",
            source_label="Sheet ventas",
        ),
        _owner_case(
            case_id="case-new",
            title="Conversaciones sin responder",
            severity="warning",
            priority_score=70,
            opened_at=datetime(2026, 5, 24, 8, tzinfo=timezone.utc),
        ),
    ]

    text = compose_owner_case_brief("Artemea", cases, report_date=date(2026, 5, 24), max_cases=3)
    final = truncate_for_whatsapp(text)

    assert len(final) <= 1000
    assert "ver reporte completo" not in final
    # Sanity: each labelled status renders in the rendered brief.
    assert "Reabierto hace 2 días" in final
    assert "Abierto hace 4 días" in final
    assert "Nuevo hoy" in final
    assert "✓ Visto" in final


def test_owner_brief_status_line_redaction_still_applies():
    from app.brain.reporting import compose_owner_case_brief

    case = _owner_case(
        case_id="case-redact",
        title="Stock crítico",
        opened_at=datetime(2026, 5, 22, 8, tzinfo=timezone.utc),
    )

    text = compose_owner_case_brief("Artemea", [case], report_date=date(2026, 5, 24))

    assert "raw_case_brief_secret" not in text
    assert "Abierto hace 2 días" in text

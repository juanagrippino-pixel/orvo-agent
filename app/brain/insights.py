"""Deterministic Orvo Brain insight engine.

LLMs may later explain these findings, but the business logic and citations
must stay deterministic.
"""

from app.brain.models import Evidence, Insight, InsightThresholds, Metric


def _metric_map(metrics: list[Metric]) -> dict[str, Metric]:
    return {metric.key: metric for metric in metrics}


def _to_float(metric: Metric | None) -> float | None:
    if metric is None:
        return None
    try:
        return float(metric.value)
    except (TypeError, ValueError):
        return None


def _merge_evidence(*metrics: Metric | None) -> list[Evidence]:
    evidence: list[Evidence] = []
    seen: set[tuple[str, str]] = set()
    for metric in metrics:
        if metric is None:
            continue
        for item in metric.evidence:
            key = (item.source, item.label)
            if key not in seen:
                evidence.append(item)
                seen.add(key)
    return evidence


def generate_insights(
    metrics: list[Metric],
    *,
    thresholds: InsightThresholds | None = None,
    revenue_drop_threshold: float | None = None,
    stock_threshold: int | None = None,
    unanswered_threshold: int | None = None,
    channel_mix_threshold: float | None = None,
    roas_threshold: float | None = None,
) -> list[Insight]:
    """Generate operational insights from cited canonical metrics.

    Thresholds can be supplied three ways, in order of precedence:
      1. Explicit keyword arguments (e.g. ``roas_threshold=2.0``).
      2. An :class:`InsightThresholds` instance via ``thresholds=...``.
      3. The defaults baked into :class:`InsightThresholds`.

    Cross-channel rules require metrics keyed as:
      - revenue_today_tn   : Tiendanube revenue today
      - revenue_today_ml   : MercadoLibre revenue today
      - orders_today_tn    : Tiendanube orders today
      - orders_today_ml    : MercadoLibre orders today
      - ad_spend_today     : Meta Ads (or any ad platform) spend today
    """

    base = thresholds or InsightThresholds()
    revenue_drop_threshold = (
        revenue_drop_threshold if revenue_drop_threshold is not None else base.revenue_drop_threshold
    )
    stock_threshold = stock_threshold if stock_threshold is not None else base.stock_threshold
    unanswered_threshold = (
        unanswered_threshold if unanswered_threshold is not None else base.unanswered_threshold
    )
    channel_mix_threshold = (
        channel_mix_threshold
        if channel_mix_threshold is not None
        else base.channel_mix_imbalance_threshold
    )
    roas_threshold = roas_threshold if roas_threshold is not None else base.roas_warning_threshold

    by_key = _metric_map(metrics)
    insights: list[Insight] = []

    # ── Existing single-channel rules ─────────────────────────────────────────

    revenue_today = _to_float(by_key.get("revenue_today"))
    revenue_baseline = _to_float(by_key.get("revenue_baseline"))
    if revenue_today is not None and revenue_baseline and revenue_baseline > 0:
        drop_ratio = (revenue_baseline - revenue_today) / revenue_baseline
        if drop_ratio >= revenue_drop_threshold:
            pct = round(drop_ratio * 100)
            insights.append(
                Insight(
                    severity="warning",
                    title=f"Ventas {pct}% debajo del promedio",
                    explanation="Las ventas de hoy están por debajo del promedio reciente.",
                    recommended_action="Revisá campañas activas, productos principales y mensajes pendientes antes de cerrar el día.",
                    evidence=_merge_evidence(by_key.get("revenue_today"), by_key.get("revenue_baseline")),
                )
            )

    stock_units = _to_float(by_key.get("stock_units"))
    if stock_units is not None and stock_units <= stock_threshold:
        insights.append(
            Insight(
                severity="critical",
                title="Stock crítico",
                explanation=f"Quedan {int(stock_units)} unidades disponibles en productos monitoreados.",
                recommended_action="Priorizá reposición o pausá campañas que empujen productos con bajo stock.",
                evidence=_merge_evidence(by_key.get("stock_units")),
            )
        )

    unanswered = _to_float(by_key.get("unanswered_conversations"))
    if unanswered is not None and unanswered >= unanswered_threshold:
        insights.append(
            Insight(
                severity="warning",
                title="Conversaciones sin responder",
                explanation=f"Hay {int(unanswered)} conversaciones pendientes que pueden frenar ventas.",
                recommended_action="Responder primero consultas de compra, envíos, talles/precios y reclamos recientes.",
                evidence=_merge_evidence(by_key.get("unanswered_conversations")),
            )
        )

    # ── Rule 1: Cross-channel revenue total ───────────────────────────────────
    # Sum TN + ML revenue and emit an informational insight with both evidences.

    tn_rev = _to_float(by_key.get("revenue_today_tn"))
    ml_rev = _to_float(by_key.get("revenue_today_ml"))

    total_revenue: float | None = None
    if tn_rev is not None and ml_rev is not None:
        total_revenue = tn_rev + ml_rev
        insights.append(
            Insight(
                severity="info",
                title="Revenue total multi-canal hoy",
                explanation=(
                    f"TN: ${tn_rev:,.0f} + ML: ${ml_rev:,.0f} = ${total_revenue:,.0f} ARS en total entre canales."
                ),
                recommended_action="Monitorear la proporción entre canales para detectar cambios de tendencia.",
                evidence=_merge_evidence(
                    by_key.get("revenue_today_tn"),
                    by_key.get("revenue_today_ml"),
                ),
            )
        )

    # ── Rule 2: Channel mix — ML dominating TN ────────────────────────────────
    # Warn if ML revenue > TN revenue by more than channel_mix_threshold (default 40%).

    if tn_rev is not None and ml_rev is not None and tn_rev > 0:
        if ml_rev > tn_rev * (1 + channel_mix_threshold):
            diff_pct = round((ml_rev - tn_rev) / tn_rev * 100)
            insights.append(
                Insight(
                    severity="warning",
                    title="Canal Tiendanube posiblemente sub-rendimiento",
                    explanation=(
                        f"MercadoLibre generó {diff_pct}% más revenue que Tiendanube hoy. "
                        f"Revisá si la tienda Tiendanube está funcionando correctamente."
                    ),
                    recommended_action=(
                        "Verificá que los productos, precios y el checkout de Tiendanube estén activos. "
                        "Considerá aumentar tráfico directo a la tienda propia."
                    ),
                    evidence=_merge_evidence(
                        by_key.get("revenue_today_tn"),
                        by_key.get("revenue_today_ml"),
                    ),
                )
            )

    # ── Rule 3: Attribution-lite (ROAS) ───────────────────────────────────────
    # ROAS = total_revenue / ad_spend. Warn if ROAS < roas_threshold.
    # Argentine ecommerce rule-of-thumb: ROAS >= 3.0 is healthy.

    ad_spend = _to_float(by_key.get("ad_spend_today"))
    if ad_spend is not None and ad_spend > 0:
        # Use cross-channel total if available, else fall back to single-channel revenue_today
        roas_revenue: float | None = total_revenue if total_revenue is not None else tn_rev
        if roas_revenue is None:
            roas_revenue = _to_float(by_key.get("revenue_today"))

        if roas_revenue is not None and roas_revenue > 0:
            roas = roas_revenue / ad_spend
            if roas < roas_threshold:
                insights.append(
                    Insight(
                        severity="warning",
                        title=f"ROAS bajo: {roas:.1f}x (mínimo recomendado {roas_threshold:.1f}x)",
                        explanation=(
                            f"Con ${ad_spend:,.0f} ARS en ads generaste ${roas_revenue:,.0f} ARS en ventas "
                            f"(ROAS {roas:.2f}x). El umbral mínimo recomendado para e-commerce argentino es {roas_threshold:.1f}x."
                        ),
                        recommended_action=(
                            "Revisá segmentación, creatividades y productos promocionados. "
                            "Pausá conjuntos de anuncios con ROAS menor a 2x y redirigí presupuesto a los de mejor rendimiento."
                        ),
                        evidence=_merge_evidence(
                            by_key.get("ad_spend_today"),
                            by_key.get("revenue_today_tn"),
                            by_key.get("revenue_today_ml"),
                            by_key.get("revenue_today"),
                        ),
                    )
                )

    # ── Rule 4: Spend without sales ───────────────────────────────────────────
    # Critical if ad_spend > 0 but combined orders_today == 0.

    if ad_spend is not None and ad_spend > 0:
        tn_orders = _to_float(by_key.get("orders_today_tn"))
        ml_orders = _to_float(by_key.get("orders_today_ml"))

        # Only fire if at least one orders metric is present
        if tn_orders is not None or ml_orders is not None:
            total_orders = (tn_orders or 0.0) + (ml_orders or 0.0)
            if total_orders == 0:
                insights.append(
                    Insight(
                        severity="critical",
                        title="Gastás en ads pero sin ventas hoy",
                        explanation=(
                            f"Se gastaron ${ad_spend:,.0f} ARS en publicidad pero no hubo ningún pedido hoy "
                            f"en ninguno de los canales monitoreados."
                        ),
                        recommended_action=(
                            "Pausá todas las campañas activas de inmediato y revisá: "
                            "landing pages, stock disponible, métodos de pago habilitados y errores en el checkout."
                        ),
                        evidence=_merge_evidence(
                            by_key.get("ad_spend_today"),
                            by_key.get("orders_today_tn"),
                            by_key.get("orders_today_ml"),
                        ),
                    )
                )

    # ── Rule 5: Stock + ads collision ─────────────────────────────────────────
    # Critical if stock_units <= stock_threshold AND ad_spend > 0.
    # (stock_units may come from existing single-channel metric or cross-channel context)

    stock_units_xc = _to_float(by_key.get("stock_units"))
    if stock_units_xc is not None and stock_units_xc <= stock_threshold:
        if ad_spend is not None and ad_spend > 0:
            # Replace the generic stock-critical insight already added above with
            # a more specific stock+ads collision insight; avoid duplicates.
            # Remove the generic stock insight if it exists.
            insights = [i for i in insights if not (i.severity == "critical" and "Stock crítico" == i.title)]
            insights.append(
                Insight(
                    severity="critical",
                    title="Ads activos con stock bajo — pausar campañas",
                    explanation=(
                        f"Quedan {int(stock_units_xc)} unidades en stock pero hay campañas activas "
                        f"con ${ad_spend:,.0f} ARS de gasto. "
                        "Seguir invirtiendo en ads con stock insuficiente genera frustración y abandono de carrito."
                    ),
                    recommended_action=(
                        "Pausar todas las campañas que promocionen productos con stock bajo. "
                        "Reactivar solo después de reponer stock o ajustar los anuncios a productos disponibles."
                    ),
                    evidence=_merge_evidence(
                        by_key.get("stock_units"),
                        by_key.get("ad_spend_today"),
                    ),
                )
            )

    return insights

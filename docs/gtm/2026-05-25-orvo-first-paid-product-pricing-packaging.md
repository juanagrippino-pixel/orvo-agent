# Orvo first paid product — Pricing & packaging

Status: PM recommendation for paid pilot / first SKU  
Date: 2026-05-25  
Scope: Tiendanube-first operations control plane; buyer pays for monitored store/control plane, daily exception desk, cases/evidence/follow-up — not seats, messages, dashboards, or generic AI chat.

Related repo sources:
- `docs/gtm/2026-05-25-tiendanube-exception-desk-pricing-packaging.md`
- `docs/research/2026-05-25-product-market-intel-tiendanube-exception-desk.md`
- `docs/research/2026-05-25-ecommerce-ops-buyer-research-tiendanube.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/d2c-action-key-catalog.md`
- `docs/specs/d2c-operator-surface-contract.md`

## Executive recommendation

Launch the first paid product as **Orvo Tiendanube Exception Desk**:

> Orvo monitors one Tiendanube store, opens evidence-backed operational cases, sends a daily WhatsApp exception brief, and keeps follow-up state/history until cases are acknowledged or resolved.

Recommended commercial motion:

1. **Sell a paid 30-day pilot at USD 149** or local equivalent at invoice time.
2. **Convert successful pilots to Starter at USD 79/mo design-partner price** for the first 3-5 logos; set **USD 99/mo as the later public Starter target** once onboarding/support COGS are known.
3. **Use Growth at USD 199/mo** when the buyer needs higher limits, more recipients/check frequency, weekly review, richer case workflow, or Meta Ads spend/order mismatch after the connector and truth gates are verified.
4. **Use Custom at USD 399+/mo scoped** for multi-store, custom connectors, marketplace/ERP/warehouse complexity, agency portfolios, or formal SLA/security/procurement.

Do not sell seats, AI messages, dashboard views, or generic automation. The paid unit is **one monitored store/control plane with a case desk**.

## Pricing anchors checked from web

Live browser/search tooling was unavailable, but HTTP fetches from known pricing URLs worked for several anchors. Treat these as sanity-check anchors to re-verify before external publication because pricing pages change and some are JS/gated.

| Anchor | Observed web pricing signal | Packaging implication for Orvo |
| --- | --- | --- |
| Tiendanube Argentina plans | Free Inicial; Esencial **ARS 24,999/mo** or **ARS 18,749.25/mo annualized**; Impulso **ARS 73,999/mo** or **ARS 55,499.25/mo annualized**; Escala **ARS 219,999/mo** or **ARS 164,999.25/mo annualized**. | Orvo cannot feel like a small Tiendanube add-on. It must anchor above the platform dashboard: evidence-backed daily operations cases and follow-up. |
| Gorgias helpdesk | Starter from **USD 10/mo** for 50 tickets; Basic **USD 50/mo** for 300 tickets; Pro **USD 300/mo** for 2,000 tickets; Advanced **USD 750/mo** for 5,000 tickets; overages. | Avoid helpdesk/ticket-volume anchoring. Orvo's unit is a monitored store and operational exceptions, not support tickets. |
| Intercom | Essential **USD 29/seat/mo**, Advanced **USD 85/seat/mo**, Expert **USD 132/seat/mo**, plus Fin outcome pricing from **USD 0.99/outcome**; add-ons around **USD 99/mo**. | Avoid per-seat/per-AI-outcome billing; keep recipients as limits only. |
| Zoko WhatsApp commerce | Starter **USD 49.99/mo**, Plus **USD 79.99/mo**, Elite **USD 139.99/mo**, Max **USD 499.99/mo**, with agents/conversation limits. | USD 79-99 Starter is plausible if Orvo is positioned as operations control, not WhatsApp inbox/CRM. |
| Triple Whale ecommerce analytics | Visible plans around **USD 179/mo**, **USD 259/mo**, **USD 539/mo**, plus GMV-based calculator examples. | Growth at USD 199/mo sits below serious analytics/BI but above simple app pricing. Do not claim attribution/BI replacement. |
| Zapier automation | Free; Professional from **USD 19.99/mo annually**; Team from **USD 69/mo annually**. | Orvo must not be priced or described as generic workflow automation; it decides and governs cases. |
| AfterShip tracking | Essentials from **USD 29/mo**, Premium from **USD 59/mo** at 6,000 shipments/year with extra shipment fees. | Shipping tools are execution systems; Orvo can surface fulfillment exceptions only when evidence is reliable. |
| ShipStation | Starter examples from **USD 14.99/mo**; higher shipment tiers scale materially. | Volume thresholds should trigger plan movement, but avoid surprise per-order overages in early GTM. |

## Value metric

Primary value metric: **one monitored Tiendanube store / operational control plane**.

This means one tenant-scoped store with store config, thresholds, freshness policy, recipients/delivery settings, Tiendanube source health, run history, evidence artifacts, deterministic Operational Cases, WhatsApp projection, and internal case/run inspection.

Secondary guardrail metrics, not primary billing units: monthly orders, active SKUs/products monitored, WhatsApp recipients/destinations, check frequency, history retention, standard connectors, and human review/support depth.

Avoid launch billing by seat, alert, WhatsApp message, LLM token, dashboard, or event. Use these only as limits and upgrade triggers.

## SKU ladder

| SKU | Buyer-facing name | Price | Target buyer | Packaging intent |
| --- | --- | ---: | --- | --- |
| Pilot | **Piloto Exception Desk Tiendanube + WhatsApp** | **USD 149 / 30 days** | First design partners; owner-operated Tiendanube physical-goods stores | Validate willingness to pay, data reliability, daily habit, case accuracy, and support load. |
| Starter | **Orvo Exception Desk Starter** | **USD 79/mo design-partner**; **USD 99/mo public target** | One Tiendanube store with manual daily checks and enough SKU/order activity | Scalable first SaaS SKU: daily exception desk for one store without ads/custom work. |
| Growth | **Orvo Exception Desk Growth** | **USD 199/mo** | Higher-volume store, more operators, ad spend, fulfillment complexity, agency involvement | Expansion tier for workflow depth, more limits, weekly review, and verified second connector/case family. |
| Custom | **Orvo Operations Control Plane Custom** | **USD 399+/mo scoped** plus setup if needed | Multi-store, multi-channel, agency portfolio, custom integration, SLA/security needs | Protect margin and roadmap when requirements exceed productized tiers. |

## Pilot offer

**Name:** Piloto Exception Desk Tiendanube + WhatsApp  
**Price:** USD 149 / 30 days or ARS equivalent at invoice time. Optional: credit USD 79-99 to first paid month only if conversion happens within 14 days after pilot end.

Buyer-facing promise in Spanish:

> Durante 30 días, Orvo mira tu Tiendanube y te manda por WhatsApp qué necesita atención: stock en riesgo, datos stale/no confiables y ventas bajo piso configurado cuando aplique. Pedidos pendientes/fulfillment se incluyen solo si validamos que los campos de pago, despacho y antigüedad son confiables para tu tienda. Cada caso viene con evidencia y seguimiento.

Included:

- 1 Tiendanube store/control plane.
- Assisted Tiendanube setup or assisted import if the connector is not self-serve for that customer.
- 1 WhatsApp destination/group.
- Up to 2 owner/operator recipients.
- 1 daily scheduled exception brief.
- Case queue/history, even if initially internal/operator-assisted.
- Source freshness/degraded-data caveats.
- Configured thresholds for stock, freshness, optional sales floor, and fulfillment aging only after field audit passes.
- One weekly 30-minute review or async case improvement note.
- Pilot concierge review, explicitly not part of the base SaaS promise.

Pilot case families:

1. **`data_stale`** — always included; trust moat when Tiendanube data is unsafe, stale, unauthorized, malformed, rate-limited, or missing required fields.
2. **`stockout_risk`** — flagship when SKU/product stock and recent sales/strategic flag are fresh and mapped.
3. **`sales_drop`** — optional/conservative; only as sales below configured floor or trustworthy baseline, never broad AI anomaly/root-cause detection.
4. **`fulfillment_backlog`** — conditional/internal until Tiendanube order/payment/fulfillment fields and owner-facing evidence gates are verified for that store.

Pilot limits:

- 30 days.
- 1 store.
- 1 commerce source: Tiendanube.
- Up to ~500 monthly orders or ~300 active SKUs as a fit boundary; larger pilots should use Growth terms.
- No Meta Ads, MercadoLibre, custom connectors, WhatsApp inbox ingestion, BI exports, ERP/warehouse/accounting integrations, or autonomous external actions.
- No guaranteed revenue lift.

## Plan limits and upgrade triggers

| Limit / capability | Pilot | Starter | Growth | Custom |
| --- | ---: | ---: | ---: | --- |
| Monitored Tiendanube stores | 1 | 1 | 1 | 2+ scoped |
| Commerce sources | Tiendanube only | Tiendanube only | Tiendanube + 1 verified standard connector when implemented | Scoped |
| WhatsApp destinations/groups | 1 | 1 | Up to 2 | Scoped |
| Recipients | Up to 2 | Up to 2 | Up to 4 | Scoped |
| Scheduled briefs/checks | 1/day | 1/day | Up to 2/day or daily + recap | Scoped |
| Monthly orders fit | ~500 | ~500 | ~2,000 | >2,000 scoped |
| Active SKUs/products monitored | ~300 | ~300 | ~1,000 | >1,000 scoped |
| Visible/inspectable history | 30 days | 90 days | 12 months | Scoped |
| Forced/manual checks | Reasonable pilot use | 1/day reasonable use | More frequent, within run policy | Scoped |
| Human review | Weekly pilot review | Setup/support only | Weekly review or async case summary | Scoped / separately priced |
| Support | Pilot concierge | Next business day setup/connector support | Priority business-hours | SLA if contracted |

Move Pilot/Starter to Growth when any of these occur: store exceeds ~500 orders/month or ~300 active SKUs; buyer asks for more recipients/groups/operators/checks; they need assignment, comments, in-progress/dismiss lifecycle, visible timeline, or agency accountability; fulfillment backlog is recurring; they want Meta Ads spend/order monitoring; they ask for weekly case review; or they need more history/accountability.

Move to Custom for multiple stores/brands/channels, custom connectors, ERP/warehouse/accounting/data warehouse/BI export requirements, marketplace/channel-mix, agency portfolio views, volumes above Growth, SLA/security/procurement, or managed-service analyst expectations.

## Pilot conversion criteria

Convert Pilot to Starter/Growth when at least **2-3** of the following are true:

- Owner/operator reads, forwards, or replies to briefs at least 3 times/week.
- At least 3 useful cases are opened/updated with evidence and accepted by the buyer as worth knowing.
- A stock, stale-data, sales-floor, or verified fulfillment exception causes a concrete action.
- Orvo replaces a manual daily check, screenshot request, or “did anyone look?” follow-up.
- Buyer asks for more recipients, workflow, ads, fulfillment depth, history, or additional checks.
- Source data is reliable enough that case false positives are manageable.
- Orvo support/onboarding load shows a path to SaaS gross margin.

Convert to **Starter** when the buyer wants the same one-store daily desk and accepts basic lifecycle. Convert to **Growth** when they ask for more workflow, volume, check frequency, recipients, review, or verified second connector. Kill/reposition when data hygiene is not fixable, most days produce no actionable cases, buyer wants dashboards/exports instead of cases, or concierge labor exceeds willingness to pay without productizable learnings.

## Exact product primitives required by SKU

### Shared primitives

| Primitive | Required shape |
| --- | --- |
| Tenant-scoped monitored store | `business_id`, store identity, timezone/currency, Tiendanube connector config, threshold policy, freshness policy, delivery settings, recipient list, store limits. |
| Connector registry entry | Tiendanube connector spec with required params, secret refs, scopes, capabilities, executor metadata, rate-limit/degraded behavior, and validation diagnostics. |
| Compiled runtime | Preview/forced/scheduled execution path that compiles business config into an execution artifact without raw secrets. |
| Tiendanube ingestion | Products/SKUs, stock, orders/revenue, timestamps, source labels, connector outcomes, and degraded/failed states. |
| Metric/evidence registry | Evidence-backed metrics for orders/revenue, inventory stock, source freshness, and later fulfillment/ads; every owner-facing number must have evidence refs. |
| Run ledger | Run start/end, trigger type, connector outcomes, artifact refs, dispatch attempts, errors, idempotency, redacted metadata. |
| OperationalCase engine | Deterministic case detection, dedupe, entity scope, severity/priority policy, evidence snapshots, lifecycle, and timeline. |
| Case lifecycle/actions | Minimum implemented actions: `acknowledge_case`, `resolve_case`. Additional action keys must not be shown as executable until handlers exist. |
| WhatsApp owner projection | Daily case brief with top open/new/resolved context, evidence/source lines, degraded caveats, allowed suggested actions, idempotent dispatch, concise Spanish copy. |
| Internal operator surface | Case queue, built-in views, run/case inspection, evidence/timeline visibility, safe mutations, redaction. |
| Admin/support controls | Threshold edit, recipient edit, manual/forced run within policy, source health inspection, safe secret handling, auditability. |

### Pilot primitives

Pilot must have these before charging a real store:

- One tenant-scoped Tiendanube store/control plane.
- Assisted Tiendanube connector setup with safe secret refs or explicitly operator-assisted import.
- Compiled runtime for scheduled daily execution; forced/manual run allowed for support.
- Run ledger sufficient to answer what ran, what failed/degraded, what was sent/skipped, and what evidence backed claims.
- `data_stale` case creation/update when source data is unsafe; stale data must suppress/narrow downstream stock/sales/fulfillment advice.
- `stockout_risk` for fresh, mapped SKUs/products using stock threshold plus recent velocity or explicit important-SKU flag; SKU-level dedupe is required before scaling beyond concierge pilot.
- Optional `sales_drop` only for configured floor or trustworthy baseline.
- `fulfillment_backlog` internal-only unless field audit passes; owner-facing requires verified paid/unfulfilled/aging semantics and redacted evidence.
- Basic lifecycle: open → acknowledged → resolved.
- WhatsApp owner brief: 1/day, 1 destination, up to 2 recipients, max top cases, source/evidence lines, degraded caveats.
- Internal operator inspection for cases/runs/evidence.
- Weekly review workflow may be manual/concierge but must be labeled pilot support.

### Starter primitives

Starter requires all Pilot primitives, productized enough to run without ongoing concierge review:

- Self-serve or repeatable assisted onboarding checklist for one Tiendanube store.
- Stable Tiendanube connector/runtime with typed degraded states.
- Run ledger and artifact inspection for 90-day history.
- Evidence-backed owner-facing case families: `data_stale`; `stockout_risk` with SKU/product evidence and dedupe; `sales_drop` only as configured sales floor/safe baseline; `fulfillment_backlog` only if that store passes truth gate and owner-facing allowlist.
- Configurable thresholds for stock, freshness, and sales floor.
- WhatsApp brief once/day, one destination, up to 2 recipients.
- Internal operator queue and built-in views for open/acknowledged/resolved, critical, data stale, and stock cases.
- Implemented lifecycle actions: `acknowledge_case`, `resolve_case` with timeline/audit.
- Redaction for secrets/tokens/URLs in logs, artifacts, cases, and run ledger.

Not required / not included in Starter: comments, assignment, `mark_in_progress`, `dismiss_case` unless implemented and audited; Meta Ads / `spend_without_orders`; MercadoLibre / marketplace / channel-mix cases; WhatsApp support inbox ingestion; BI exports; custom dashboards; ERP/accounting/warehouse connectors; autonomous external actions.

### Growth primitives

Growth requires Starter plus the following; do not sell a Growth claim until each primitive is implemented/verified or explicitly contracted as roadmap:

- Higher limits: up to ~2,000 orders/month, ~1,000 SKUs, up to 4 recipients, up to 2 daily check windows, 12 months history.
- Richer case workflow: `add_comment`, `assign_owner`, in-progress/dismiss lifecycle states only after status model/transitions exist, and visible case timeline for evidence/comments/actions/status/run refs.
- Priority business-hours source-health monitoring and support.
- Weekly case review or async operational summary.
- One additional standard connector only when implemented and truth-gated; expected first expansion: Meta Ads.
- `spend_without_orders` only after Meta Ads + Tiendanube freshness parity is trustworthy, with simple evidence: ad spend above threshold and orders/revenue below configured range.
- Deeper `fulfillment_backlog` workflow only after Tiendanube fields prove reliable and owner-facing evidence is safe.

Not included in Growth: unlimited stores/channels/connectors; bespoke ERP/accounting/warehouse connector work; full BI/dashboard replacement; full WhatsApp inbox/chatbot suite; 24/7 SLA unless contracted; guaranteed revenue lift.

### Custom primitives

Custom includes a scoped subset/superset of Growth, priced to protect implementation and support margin:

- Multi-store or multi-brand tenant model and portfolio/operator views.
- Multiple WhatsApp destinations, teams, or agency/client partitions.
- Custom connector implementation or certification gates.
- Marketplace/channel-mix cases after source freshness parity.
- Longer retention, audit export, security review, procurement, or data residency requirements.
- SLA/support commitments and incident procedures.
- Optional managed review/analyst service, priced separately from SaaS.

Custom must still obey platform contracts: no LLM-created metrics/detections/priorities/lifecycle transitions; no unsupported owner-facing numbers; no external side effects without approval, idempotency, audit, and rollback/inspection semantics.

## Packaging risks

1. **Cheap-app anchoring.** USD 79-99 feels high if positioned as an alert/report app. Lead with operational cases, evidence, and follow-up memory.
2. **Helpdesk/WhatsApp inbox anchoring.** Competitors price by agents, tickets, or conversations. Orvo should not be compared to an inbox; recipients are limits, not value metric.
3. **Dashboard/BI anchoring.** Analytics tools sell dashboards and attribution. Orvo sells exception management and lifecycle state.
4. **Undercharging concierge labor.** The USD 149 pilot can become unprofitable if setup/review is heavy. Track onboarding minutes, connector failures, manual checks, and support touches.
5. **Starter price too low for high-touch customers.** If pilots need ongoing review, convert them to Growth or a USD 149/mo continuation rather than forcing USD 79/mo.
6. **Argentina FX/inflation.** Use USD reference pricing or ARS equivalents with short validity windows; avoid long fixed ARS commitments.
7. **Low-volume churn.** Very small stores may like the idea but lack urgency. Qualify for physical goods, real SKU/order volume, and a named follow-up owner.
8. **Fulfillment data reliability.** Do not make pending-order claims until Tiendanube fields for payment, fulfillment, cancellations/refunds, timestamps, and source-of-truth boundaries are verified.
9. **Sales-drop noise.** Keep `sales_drop` threshold-based and conservative; do not sell broad anomaly/root-cause certainty.
10. **Meta Ads pull.** Ads have clear ROI but can drag Orvo into attribution disputes. Sell only `spend_without_orders` after source freshness parity, not ROAS truth.
11. **WhatsApp delivery constraints/cost.** Template approvals, provider fees, delivery failures, and per-message costs can affect margin. Keep recipient/frequency limits explicit.
12. **Custom connector pull.** SMBs will ask for MercadoLibre, ERP, sheets, accounting, shipping, and WhatsApp inboxes. Route to Growth/Custom; do not pollute Starter.
13. **Unsupported product claims.** Current repo supports only basic lifecycle (`open`, `acknowledged`, `resolved`) and does not yet include owner-facing `fulfillment_backlog` as implemented. Package future workflow only behind implementation gates.
14. **Per-order overage sensitivity.** Use volume thresholds for plan movement rather than surprise overages in early GTM.
15. **ROI proof lag.** Do not guarantee revenue lift. Prove value through cases caught, manual checks replaced, stale data surfaced, and follow-up closed.

## Sales offer to use now

> **Piloto Exception Desk Tiendanube + WhatsApp — USD 149 / 30 días.** 1 tienda, resumen operativo diario por WhatsApp, casos con evidencia para stock en riesgo, datos stale/no confiables y ventas bajo piso configurado. Pedidos pendientes/fulfillment se agregan solo cuando validamos que el dato de pago/despacho lo permite. Incluye setup asistido y revisión semanal. Si sirve, pasás a Starter USD 79/mes como design partner o Growth USD 199/mes según volumen y workflow.

Short positioning:

> Orvo no es otro dashboard ni un bot. Es una cola operativa diaria para Tiendanube: qué necesita atención hoy, por qué, con qué evidencia y quién lo sigue hasta resolverlo.

## Immediate PM/engineering gates before broader rollout

1. SKU-level `stockout_risk` evidence and dedupe: `<business_id>/stockout_risk/sku/<sku_or_product_id>/commerce.inventory/daily`.
2. Owner-facing case allowlist/readiness gate so internal/conditional cases never leak into WhatsApp claims.
3. Robust `data_stale` suppression/narrowing for stock, sales, and fulfillment advice.
4. Tiendanube fulfillment field audit on 2-3 real/sandbox stores before making `fulfillment_backlog` owner-facing.
5. Repeatable onboarding/support checklist with minutes tracked against pilot price.
6. Pricing validation: ask for 3 paid pilots at USD 149 and measure whether conversion goes to USD 79/99 Starter, USD 199 Growth, or requires managed-service pricing.

# Orvo Tiendanube Exception Desk — Pricing & Packaging Revision

Status: PM hypothesis for paid pilot / early GTM  
Date: 2026-05-25  
Related: `docs/gtm/d2c-pricing-packaging-hypothesis.md`, `docs/product/tiendanube-exception-desk-opportunity-spec.md`, `docs/research/2026-05-24-orvo-competitor-landscape.md`, `docs/research/2026-05-24-tiendanube-latam-d2c-buyer-pain-icp.md`

## Executive recommendation

Keep the current price ladder as the working hypothesis, but sharpen the package around the buyer-facing job:

> **Orvo Tiendanube Exception Desk** watches one Tiendanube store and sends a daily WhatsApp exception brief: stock risk, stale/unsafe data, and conservative sales-floor exceptions — each backed by evidence and follow-up history. Pending-order/fulfillment cases are included only after Orvo verifies the store's Tiendanube payment/fulfillment fields.

Recommended launch motion:

1. **Sell a paid 30-day pilot at USD 149** to validate willingness to pay, onboarding burden, source reliability, and daily operator habit.
2. **Convert to Starter at USD 79/mo** for one Tiendanube store/control plane, not per seat.
3. **Use Growth at USD 199/mo** when the customer needs workflow depth, more recipients/checks, higher volume, Meta Ads expansion, weekly review, or stronger case lifecycle.
4. **Reserve Custom at USD 399+/mo** for multi-store, custom connectors, multi-channel, agency portfolio, or SLA/security requirements.

Do not publish as a generic analytics dashboard, chatbot, helpdesk, or automation tool. Package the product as a daily operational exception desk.

## Verification note and source URLs

Live web-search was requested for price sanity-checking, but this execution environment did not expose a web-search/browser tool. The URLs below are the places to verify exact current pricing and packaging before using this externally. Do **not** quote exact current competitor or Tiendanube prices until verified.

### Tiendanube / Nuvemshop pricing and ecosystem anchors to verify

- Tiendanube pricing/plans: https://www.tiendanube.com/planes-y-precios
- Tiendanube App Store: https://www.tiendanube.com/tienda-aplicaciones-nube
- Tiendanube gestión apps: https://www.tiendanube.com/tienda-aplicaciones-nube/categorias/gestion
- Tiendanube envíos apps: https://www.tiendanube.com/tienda-aplicaciones-nube/categorias/envios
- Tiendanube WhatsApp selling / WhatsApp Business education: https://www.tiendanube.com/blog/como-vender-por-whatsapp/ and https://www.tiendanube.com/blog/whatsapp-business/
- Tiendanube help: WhatsApp button / assistant: https://ayuda.tiendanube.com/es_AR/123362-whatsapp/como-agregar-el-boton-de-whatsapp-en-mi-tiendanube and https://ayuda.tiendanube.com/es_AR/configurar-tu-asistente/como-conectar-mi-asistente-virtual-a-whatsapp-para-que-empiece-a-responder

### Adjacent pricing anchors to verify

These should be used only as category anchors, not direct comps:

- Ecommerce analytics / attribution: Triple Whale https://www.triplewhale.com/pricing, Polar Analytics https://www.polaranalytics.com/pricing, BeProfit Shopify app https://apps.shopify.com/beprofit-profit-tracker
- Helpdesk / ecommerce support: Gorgias https://www.gorgias.com/pricing, Zendesk https://www.zendesk.com/pricing/, Intercom Fin https://www.intercom.com/pricing, Re:amaze https://www.reamaze.com/pricing
- WhatsApp inbox / marketing / CRM: WATI https://www.wati.io/pricing/, Zoko https://www.zoko.io/pricing, Manychat https://manychat.com/pricing, Zenvia https://www.zenvia.com/
- Workflow automation / iPaaS: Zapier https://zapier.com/pricing, Make https://www.make.com/en/pricing, n8n https://n8n.io/pricing
- Ecommerce ops apps: AfterShip https://www.aftership.com/pricing, ShipStation https://www.shipstation.com/pricing/, Inventory Planner https://www.inventory-planner.com/pricing/, Mechanic https://mechanic.dev/pricing/
- Tiendanube ecosystem examples from repo research: Dux ERP https://www.tiendanube.com/tienda-aplicaciones-nube/dux-software-erp, Alerti https://www.tiendanube.com/tienda-aplicaciones-nube/alerti-app, Producteca https://www.tiendanube.com/tienda-aplicaciones-nube/producteca, BaseLinker https://www.tiendanube.com/tienda-aplicaciones-nube/baselinker

## Market sanity-check implications

Pending live price verification, the packaging implications remain:

- **Avoid cheap-app anchoring.** If buyers compare Orvo to a single Tiendanube utility app, USD 79/mo may feel high. The sales narrative must anchor on operational cases, evidence, follow-up, and replacing daily manual checks.
- **Avoid helpdesk per-seat anchoring.** Helpdesks often price by seat or support volume, but Orvo's value object is one monitored store/control plane. Keep seat counts as soft limits, not the main meter.
- **Avoid BI/dashboard anchoring.** Analytics tools compete on dashboards and attribution; Orvo should charge for exception management and workflow state.
- **Stay below agency/BI retainer territory for the first SKU.** USD 79-199/mo is plausible as an SMB SaaS wedge if it saves owner time and catches operational risk without becoming concierge labor.
- **Use USD reference pricing and ARS equivalent at invoice time.** Argentina FX/inflation risk makes long fixed ARS commitments dangerous. Use short validity windows or prepaid periods.

## Value metric

Primary value metric: **one monitored Tiendanube store / operational control plane**.

Why:

- The durable value unit is a store's operational state: connectors, run history, evidence, cases, recipients, and follow-up.
- It avoids per-seat friction for small teams and agencies.
- It maps naturally to expansion: more stores, more channels/connectors, more case families, more workflow depth, and higher operational volume.

Secondary/guardrail metrics:

- Monthly orders.
- Active SKUs/products monitored.
- WhatsApp recipients/destinations.
- Scheduled brief/check frequency.
- Case history retention.
- Standard connectors enabled.
- Human review/support depth.

Avoid launch billing by event, alert, AI message, or seat. Use those as limits/upgrade triggers.

## Revised SKU/package hypothesis

| SKU | Buyer-facing name | Target customer | Price hypothesis | Packaging intent |
| --- | --- | --- | --- | --- |
| Pilot | **Piloto Exception Desk Tiendanube + WhatsApp** | First design partners; owner-operated Tiendanube stores | **USD 149 / 30 days** or ARS equivalent at invoice time; optionally creditable to first paid month | Validate daily habit, willingness to pay, setup time, case accuracy, source freshness, and support load |
| Starter | **Orvo Exception Desk Starter** | One Tiendanube store with manual daily ops | **USD 79/mo** or ARS equivalent; optional setup fee after design-partner phase | First scalable SaaS package: daily Tiendanube exception desk without ads/custom work |
| Growth | **Orvo Exception Desk Growth** | Higher-volume store or team with more operators, ad spend, fulfillment complexity, or agency involvement | **USD 199/mo** or ARS equivalent; optional onboarding fee | Expansion tier for workflow depth, more volume/recipients/checks, and Meta Ads or fulfillment expansion when verified |
| Custom | **Orvo Operations Control Plane Custom** | Multi-store, multi-channel, custom connector, agency portfolio, formal SLA/security | **USD 399+/mo** scoped | Protect margin and roadmap when requirements exceed productized tiers |

### Design-partner discount

If needed, offer the first 3-5 logos **Starter at USD 49-59/mo for 3 months** in exchange for weekly feedback and permission to use anonymized learnings. Avoid permanent low-price grandfathering.

## Pilot offer

### Piloto Exception Desk Tiendanube + WhatsApp — USD 149 / 30 days

Buyer-facing promise:

> Durante 30 días, Orvo mira tu Tiendanube y te manda por WhatsApp qué necesita atención: stock en riesgo, datos stale/no confiables y ventas bajo piso configurado cuando aplique. Pedidos pendientes/fulfillment se incluyen solo si validamos que los campos de pago, despacho y antigüedad son confiables para tu tienda. Cada caso viene con evidencia y seguimiento.

Included:

- Assisted Tiendanube setup or assisted data import if the connector is not fully self-serve.
- 1 Tiendanube store.
- 1 WhatsApp destination/group.
- Up to 2 owner/operator recipients.
- 1 daily scheduled exception brief.
- Evidence-backed case queue/history, even if initially internal/operator-assisted.
- Source freshness / degraded-data caveats.
- Threshold configuration for stock, freshness, optional sales floor, and fulfillment aging only after the fulfillment data audit passes.
- One weekly 30-minute review or async improvement note.
- Pilot concierge review, explicitly framed as pilot support and **not** part of the base SaaS promise.

Pilot case families:

1. **`stockout_risk`** — flagship case if product/SKU and stock data are fresh.
2. **`data_stale`** — always included; core trust moat.
3. **`sales_drop`** — optional/conservative, only when there is an explicit configured floor or trustworthy baseline. Do not sell broad anomaly detection or root-cause certainty.
4. **`fulfillment_backlog`** — conditional/internal until Tiendanube order/payment/fulfillment fields and owner-facing evidence gates are verified for that store.

Pilot limits:

- 30 days.
- 1 store.
- 1 commerce source: Tiendanube.
- Up to ~500 monthly orders or ~300 active SKUs as a fit signal; larger stores should pilot on Growth terms.
- No Meta Ads, MercadoLibre, custom connectors, helpdesk/WhatsApp inbox ingestion, BI exports, or autonomous external actions.
- No guaranteed revenue lift.

Pilot conversion criteria:

Convert when at least 2 of these are true:

- Owner/operator reads, forwards, or replies to briefs repeatedly.
- At least 3 useful cases are opened/updated with evidence.
- A stock, fulfillment, or stale-data exception creates a concrete action.
- Orvo replaces a manual daily check or screenshot request.
- Buyer asks for more recipients, workflow, ads, fulfillment depth, history, or additional checks.

## Starter package — Orvo Exception Desk Starter

Target buyer: one Tiendanube store where the owner/operator wants the daily answer: **“qué necesita atención hoy?”**

Included:

- Tiendanube connector/runtime.
- Daily WhatsApp exception brief.
- Deterministic case queue/history.
- Evidence snapshots behind every owner-facing number.
- Run ledger/source-health inspection for Orvo/operator support.
- Configured thresholds.
- Data freshness/degraded alerts.
- Basic case lifecycle: open, acknowledged, resolved via implemented `acknowledge_case` and `resolve_case` actions. Comments, assignment, in-progress, and dismissed states are Growth/workflow roadmap until implemented.
- Case families:
  - `stockout_risk`.
  - `data_stale`.
  - `fulfillment_backlog` only after Tiendanube fulfillment fields are verified for the customer and the case is explicitly owner-facing ready.
  - `sales_drop` only as configured sales floor / conservative optional case.

Starter limits:

- 1 Tiendanube store.
- 1 commerce source.
- 1 scheduled brief/day.
- 1 WhatsApp destination/group.
- Up to 2 recipients.
- Up to ~500 orders/month.
- Up to ~300 active SKUs/products monitored.
- Up to 90 days of case/run history visible or inspectable.
- Standard support: next business day for setup/connector issues.
- Reasonable-use manual/forced checks; default cap 1/day unless needed for support.

Not included in Starter:

- Meta Ads connector or `spend_without_orders`.
- MercadoLibre / marketplace / channel-mix cases.
- WhatsApp support inbox ingestion or `unanswered_conversations` unless a real connector exists and is separately packaged.
- Custom dashboards, BI exports, data warehouse, ERP/accounting/warehouse integration.
- Multi-store or agency portfolio views.
- Autonomous external actions: pausing ads, changing stock/prices, sending customer messages, editing Tiendanube, refunds, cancellations.
- Unlimited history, SKUs, checks, recipients, or human review.

## Growth package — Orvo Exception Desk Growth

Target buyer: a D2C store where missed exceptions are materially expensive: more orders/SKUs, active ad spend, multiple operators, fulfillment complexity, or agency involvement.

Included: everything in Starter, plus:

- Workflow depth when implemented:
  - acknowledge / resolve now, with in-progress / dismiss only after lifecycle implementation lands;
  - comments after an `add_comment` handler exists;
  - assignment after an `assign_owner` handler exists;
  - visible case timeline after the operator surface exposes timeline events.
- Two daily brief/check windows or daily brief + exception recap.
- Up to 4 recipients.
- Up to ~2,000 orders/month.
- Up to ~1,000 active SKUs/products monitored.
- Up to 12 months case/run history.
- Weekly case review: 30 minutes or async summary.
- Stronger freshness monitoring and priority business-hours support.
- One additional standard connector when implemented and verified; expected first expansion: Meta Ads.
- Growth case families when implemented and source freshness parity is trustworthy:
  - `spend_without_orders` for Meta Ads + Tiendanube.
  - deeper `fulfillment_backlog` workflow.
  - later `channel_mix_shift` only after multi-channel sources are reliable.

Not included in Growth:

- Unlimited stores/channels/connectors.
- Bespoke ERP/accounting/warehouse connector work.
- Full BI/dashboard replacement.
- Full customer support inbox/chatbot suite.
- 24/7 SLA unless separately contracted.
- Developer marketplace, SDK, or generic automation platform.
- Guaranteed revenue lift.

## Custom package — Orvo Operations Control Plane Custom

Use Custom when productized tiers would be distorted.

Typical triggers:

- Multiple Tiendanube stores or brands.
- MercadoLibre/marketplace/channel-mix requirements.
- Custom connector, ERP, data warehouse, or agency portfolio view.
- More than ~2,000 orders/month or ~1,000 active SKUs per monitored store.
- More than 4 recipients, multiple WhatsApp destinations, or multiple operator teams.
- Formal SLA, security review, procurement, audit/export, retention, or data residency requirements.
- Concierge analyst / daily human operator expectations.

Custom should start at **USD 399+/mo scoped**, with setup/onboarding priced separately when integration work is non-trivial.

## Expansion triggers

Move Pilot/Starter to Growth when any of these occur:

- Store exceeds ~500 orders/month or ~300 active SKUs.
- Buyer asks for more than 2 recipients, more than 1 WhatsApp group, or multiple operators.
- They need case assignment, comments, in-progress status, visible timeline, or accountability by operator/agency.
- They need more than one daily scheduled brief/check.
- Fulfillment backlog is recurring and needs workflow, not just a daily mention.
- They run meaningful Meta Ads spend and ask “gastamos pero no entran pedidos?” A good rule of thumb: one bad ad day can exceed Orvo's monthly price.
- They ask for weekly case review or operational recommendations.
- They want more history, recurring trend review, or owner/agency accountability.

Move to Custom when:

- Multiple stores/brands/channels become required.
- Custom connectors or data work becomes required.
- Volume exceeds Growth limits.
- Procurement/SLA/security requirements appear.
- The buyer expects a managed service or agency-style analyst, not SaaS.

## Pricing risks

1. **Exact market prices unverified.** Tiendanube plan/app and competitor prices must be checked live before external publication.
2. **Cheap-app anchoring.** USD 79/mo may feel high if positioned as a report app. Position as daily exception desk with evidence and follow-up.
3. **Undercharging concierge labor.** USD 149 pilot can be unprofitable if setup/review is heavy. Track onboarding minutes, manual checks, connector failures, and support touches.
4. **Argentina FX/inflation.** Avoid long fixed ARS commitments. Use USD reference or short-validity ARS equivalents.
5. **Low-volume churn.** Very small stores may like the product but not feel enough economic urgency. Use minimum fit criteria.
6. **Fulfillment data reliability.** If Tiendanube fields are incomplete or not maintained by the merchant, `fulfillment_backlog` can create false confidence. Suppress or keep out when not reliable.
7. **Sales-drop noise.** `sales_drop` is easy to understand but noisy without baseline/root-cause evidence. Keep conservative and threshold-based.
8. **Meta Ads pull.** Ads may be clearest ROI but can drag Orvo into attribution debates. Use `spend_without_orders` only with freshness parity and simple evidence.
9. **WhatsApp delivery constraints/costs.** Template approvals, provider fees, delivery failures, and per-message costs can affect margin. Keep recipients and brief frequency explicit.
10. **Custom connector pull.** SMBs will ask for MercadoLibre, ERP, sheets, accounting, shipping, and WhatsApp inboxes. Saying yes too early breaks margin and focus.
11. **Per-order overage sensitivity.** Use volume thresholds for plan movement rather than surprise overages.
12. **ROI proof lag.** Avoid revenue-lift guarantees. Prove value through cases caught, manual checks replaced, stale data surfaced, and follow-up history.

## Recommended first sales offer

> **Piloto Exception Desk Tiendanube + WhatsApp — USD 149 / 30 días.** 1 tienda, resumen operativo diario por WhatsApp, casos con evidencia para stock en riesgo, datos stale/no confiables y ventas bajo piso configurado. Pedidos pendientes/fulfillment se agregan solo cuando validamos que el dato de pago/despacho lo permite. Incluye setup asistido y revisión semanal. Si sirve, pasás a Starter USD 79/mes o Growth USD 199/mes según volumen y workflow.

Short positioning:

> Orvo no es otro dashboard ni un bot. Es una cola operativa diaria para Tiendanube: qué necesita atención hoy, por qué, con qué evidencia y quién lo sigue hasta resolverlo.

## What needs verification before publishing

- Current Tiendanube Argentina and LatAm plan pricing and billing terms.
- Current Tiendanube app-store prices for alerting, ERP-lite, shipping, WhatsApp, and marketplace apps.
- Current prices and packaging for helpdesk, WhatsApp CRM, ecommerce analytics, inventory/fulfillment, and automation tools listed above.
- WhatsApp Business Platform/provider fees and template constraints for the intended delivery path.
- Whether Tiendanube order/payment/fulfillment fields and owner-facing evidence gates are reliable enough to include `fulfillment_backlog` as an owner-facing add-on for each pilot.
- Actual Orvo COGS: onboarding minutes, support minutes, WhatsApp delivery cost, connector retries, run frequency, storage, and manual review.

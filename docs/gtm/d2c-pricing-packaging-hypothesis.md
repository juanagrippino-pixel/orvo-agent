# Orvo Tiendanube Control Plane Pricing / Packaging Hypothesis

Status: Draft GTM hypothesis  
Date: 2026-05-24  
Related: `docs/gtm/d2c-packaging-and-messaging.md`, `docs/product/d2c-control-plane-prd.md`

## Goal

Create the first paid package for Orvo's narrow/deep wedge: Tiendanube + WhatsApp ecommerce operations control plane for Argentine/LatAm D2C SMBs.

This is a pricing hypothesis, not a published price sheet. Exact ARS amounts should be refreshed at sales time because Argentina inflation/FX can move faster than product learning.

## Market sanity check

Web sanity-check was requested, but this environment does not expose a web-search tool. The hypothesis below uses broad SMB SaaS anchor ranges that should be verified before publishing:

- SMB ecommerce apps often anchor low, roughly app-store style monthly pricing, and buyers are sensitive below/around the cost of their commerce platform plan.
- Helpdesk/support tools commonly anchor per seat; small teams may accept a larger total bill when tied to customer conversations, but Orvo should avoid per-seat pricing at launch because the buyer value is store monitoring, not seats.
- Analytics/reporting apps often price by data source, volume, or reporting depth; Orvo should not be sold as "another dashboard" or it will be compared to cheaper report/export tools.
- Automation tools often price by tasks/runs/connectors; useful as a COGS/limits analogy, but risky as the buyer story because Orvo is not promising full automation yet.

Implication: first paid Orvo should sit above cheap app-store utilities, below agency/BI retainers, and charge by store + operational complexity rather than seats.

## Packaging principles

1. **Bill by store/control plane, not by user.** The unit of value is one Tiendanube operation being watched.
2. **Use USD reference pricing, invoice in ARS equivalent where needed.** Avoid long fixed ARS commitments unless prepaid with a clear adjustment clause.
3. **Keep Starter narrow.** Tiendanube, daily WhatsApp brief, cases, evidence, freshness, history. Do not include ads, custom dashboards, broad connectors, or automation.
4. **Make Growth the cross-system/ops-workflow tier.** Ads mismatch, operator comments/actions, more recipients, stronger freshness monitoring/support response, weekly review.
5. **Use soft limits first.** Argentina/LatAm SMB buyers dislike surprise overages. Use limits as expansion triggers, not punitive per-event billing.
6. **Pilot must be paid.** Free pilots will validate curiosity, not willingness to pay.

## SKU hypothesis

| SKU | Buyer-facing name | Target customer | Hypothesis price | Packaging intent |
| --- | --- | --- | --- | --- |
| Pilot | **Piloto Tiendanube + WhatsApp** | First design partners; owner-operated store | **USD 149 for 30 days** or ARS equivalent, optionally creditable to first paid month | Validate daily usefulness, onboarding burden, case accuracy, willingness to pay |
| Starter | **Orvo Operaciones Starter** | Small D2C store with one Tiendanube store and manual ops | **USD 79/mo** or ARS equivalent; optional USD 99 setup after design-partner phase | First scalable paid product; daily operating queue without ads/custom work |
| Growth | **Orvo Operaciones Growth** | Store with more SKUs/orders, ad spend, operator follow-up, or agency complexity | **USD 199/mo** or ARS equivalent; optional USD 199 onboarding | Expansion tier for cross-system cases and workflow depth |
| Custom | **Orvo Control Plane Custom** | Multi-store, multi-channel, custom connector, agency-managed operations | **USD 399+/mo** scoped | Do not lead with this; use only when Starter/Growth limits are structurally exceeded |

Design-partner discount option: first 3-5 logos can get Starter at USD 49-59/mo for 3 months in exchange for weekly feedback and permission to use anonymized learnings. Avoid permanent low-price grandfathering.

## Pilot package: Piloto Tiendanube + WhatsApp

### Included

- Assisted Tiendanube connector setup or assisted import.
- One Tiendanube store.
- One WhatsApp owner/operator brief per business day or daily scheduled brief, depending on operational reliability.
- 3 launch case families when ready and verified:
  - `sales_drop`
  - `stockout_risk`
  - `data_stale`
- Evidence-backed case queue/history, initially internal/operator-assisted if the self-serve surface is not polished.
- Run health / degraded-data caveats.
- Configured thresholds for sales minimums, stock risk, and freshness.
- One weekly 30-minute review or async improvement note.
- Manual operator review/follow-up during pilot, explicitly framed as pilot concierge and not part of the base SaaS promise.

### Pilot limits

- 30 days.
- 1 store.
- 1 commerce source: Tiendanube.
- 1 WhatsApp destination/group.
- Up to 2 operator recipients.
- Up to 500 monthly orders or 300 active SKUs as a practical fit signal; larger stores should pilot on Growth terms.
- No custom connectors.
- No guaranteed revenue lift.

### Pilot success criteria

Convert if at least 2 of the following happen:

- Owner/operator reads or reacts to briefs repeatedly.
- At least 3 useful cases are opened/updated with evidence.
- At least one stale/degraded-data case avoids a bad recommendation.
- Owner says Orvo replaced a manual daily check.
- Owner asks for ads, fulfillment, multiple recipients, or follow-up tracking.

## Starter package: Orvo Operaciones Starter

### Target buyer

One Tiendanube store where the owner/operator wants a daily answer to: "qué necesita atención hoy?" They are not yet buying a full ops platform or BI tool.

### Included primitives

- Tiendanube connector/runtime.
- Daily WhatsApp operating brief.
- Case queue/history for deterministic cases.
- Run ledger inspection for Orvo/operator support.
- Metric/evidence snapshots behind every owner-facing number.
- Configured thresholds.
- Data freshness/degraded alerts.
- Basic case lifecycle: open, update, resolved/dismissed by operator-assisted process or minimal surface when available.
- 3 launch case families:
  - `sales_drop`
  - `stockout_risk`
  - `data_stale`
- Suggested actions from registered action keys only:
  - `check_storefront`
  - `confirm_stock`
  - `pause_promotion` as recommendation only
  - `refresh_credentials`
  - `retry_connector` when safe

### Starter limits

- 1 Tiendanube store.
- 1 scheduled brief/day.
- Up to 2 WhatsApp recipients.
- Up to 500 orders/month.
- Up to 300 active SKUs/products monitored for stock risk.
- Up to 90 days of case/run history visible/inspectable.
- Standard support: next business day for setup/connector issues.
- Reasonable-use forced/manual checks; default cap 1/day unless needed for support.

### What NOT to include in Starter

- Meta Ads connector or `spend_without_orders` cases.
- MercadoLibre/marketplace/channel-mix cases.
- WhatsApp support inbox ingestion or `unanswered_conversations` unless a real connector exists.
- Custom dashboards or BI exports.
- Custom connectors, ERP/accounting/warehouse integration, payment reconciliation.
- Multi-store or agency portfolio views.
- Autonomous external actions: pausing campaigns, changing stock, sending customer messages, editing Tiendanube.
- SLA promises beyond honest freshness/degraded behavior.
- Dedicated analyst/weekly business review.
- Unlimited history, unlimited SKUs, or unlimited manual checks.

## Growth package: Orvo Operaciones Growth

### Target buyer

A D2C store that has enough complexity that missed signals are expensive: more orders/SKUs, active ad spend, multiple operators, fulfillment issues, or an agency involved.

### Included primitives

Everything in Starter, plus:

- More operator workflow depth:
  - comments
  - assignment
  - acknowledge / in-progress / resolve / dismiss
  - case timeline visible to operator
- Weekly case review: 30 minutes or async Loom/message summary.
- Stronger freshness monitoring and faster support response.
- Additional case families when implemented and verified:
  - `fulfillment_backlog` from Tiendanube order/fulfillment data
  - `spend_without_orders` only after Meta Ads + Tiendanube freshness parity is trustworthy
  - `channel_mix_shift` only after multi-channel sources are reliable
- One additional connector when available, expected first expansion: Meta Ads.
- Two daily scheduled brief windows or daily brief + exception recap.
- More recipients and operator seats without per-seat nickel-and-diming.

### Growth limits

- 1 Tiendanube store included; additional stores require Custom or add-on.
- Up to 2,000 orders/month.
- Up to 1,000 active SKUs/products monitored.
- Up to 4 WhatsApp recipients.
- Up to 2 scheduled briefs/day.
- Up to 12 months case/run history.
- 1 additional standard connector when supported, likely Meta Ads.
- Priority support during business hours.

### What NOT to include in Growth

- Unlimited stores/channels/connectors.
- Bespoke ERP/accounting/warehouse work as part of base price.
- Fully automated ad, stock, price, order, or customer-message actions.
- Custom ML forecasting or revenue-lift guarantees.
- Full BI/dashboard replacement.
- Dedicated daily human operator or agency-style account management.
- 24/7 SLA.
- Support inbox/chatbot automation unless separately scoped.
- Developer marketplace, SDK, or generic workflow platform positioning.

## Expansion triggers

Move a customer from Pilot/Starter to Growth when any of these occur:

- Store exceeds ~500 orders/month or ~300 active SKUs.
- Owner asks for more than 2 WhatsApp recipients or multiple operators.
- They want comments, assignment, resolve/dismiss workflow, or case timeline access.
- They run meaningful Meta Ads spend and ask "spent but no orders?"; rough trigger: ad spend high enough that one bad day exceeds the monthly Orvo price.
- They need more than one daily brief/check.
- Fulfillment backlog becomes a recurring pain.
- They ask for weekly review of cases and recommended operational changes.
- They have an agency/operator who needs evidence and follow-up history.

Move to Custom when:

- Multiple Tiendanube stores or brands.
- Marketplace/channel-mix requirements.
- Custom connector or data warehouse work.
- More than ~2,000 orders/month or ~1,000 active SKUs.
- Formal SLA/security/procurement requirements.

## Add-on hypothesis, not launch default

Do not lead with add-ons, but keep these for later pricing tests:

- Additional Tiendanube store: USD 49-99/mo depending on complexity.
- Additional standard connector after verified: USD 49/mo.
- Extra weekly review / concierge ops: USD 100-250/mo.
- Historical backfill/import beyond default: one-time scoped setup.
- Agency portfolio view: Custom.

## Pricing risks

1. **Cheap-app anchoring.** If Orvo is perceived as a Tiendanube report app, USD 79 may feel high. Sales must anchor on daily operating cases, evidence, follow-up, and reduced manual checks.
2. **Undercharging concierge work.** USD 149 pilot can be unprofitable if setup/review is heavy. Track onboarding minutes, connector failures, and manual review time from day one.
3. **Argentina FX/inflation.** Fixed ARS prices can become wrong quickly. Use USD reference or short ARS validity windows.
4. **Low-volume stores will not feel urgency.** Very small stores may like the brief but churn because missed signals are not costly enough. Use minimum fit criteria.
5. **Ads may be the clearest ROI.** Starter without Meta Ads is narrower; avoid overpromising until `spend_without_orders` is reliable, but treat ads as a strong Growth expansion trigger.
6. **Data quality/API reliability.** Tiendanube freshness and product/order data gaps can create support load. Price must include degraded honesty, not manual heroics forever.
7. **WhatsApp delivery constraints/costs.** Template, phone, and message costs can affect gross margin and reliability. Keep recipient/brief limits explicit.
8. **Custom connector pull.** SMBs will ask for MercadoLibre, sheets, ERP, fulfillment, accounting. Saying yes too early breaks the narrow wedge and COGS.
9. **ROI proof lag.** Avoid guaranteed revenue-lift claims. Prove value through cases caught, manual checks replaced, stale data surfaced, and follow-up history.
10. **Per-order overage sensitivity.** Use volume thresholds for plan movement instead of surprise overages.

## Recommended first offer

Lead with:

> Piloto Tiendanube + WhatsApp: USD 149 / 30 días, 1 tienda, resumen operativo diario, 3 familias de casos con evidencia, configuración asistida y revisión semanal. Si te sirve, pasás a Starter USD 79/mes o Growth USD 199/mes según complejidad.

Spanish positioning:

> Orvo te arma una cola operativa diaria: qué pasó, qué importa, por qué, y qué sigue. Tiendanube + WhatsApp primero; casos con evidencia, no otro dashboard.

Do not publish Custom pricing initially. Use it only to avoid distorting Starter/Growth when a larger customer asks for multi-store or custom integrations.

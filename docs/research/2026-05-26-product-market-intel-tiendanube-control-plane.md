# Product & Market Intelligence — Tiendanube Control Plane Sellable Opportunities

Date: 2026-05-26  
Status: Product & Market Intelligence synthesis  
Scope: First paid product for Orvo as a Tiendanube-first ecommerce operations control plane.  
Related:
- `docs/README.md`
- `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/product/tiendanube-exception-desk-opportunity-spec.md`
- `docs/gtm/2026-05-25-orvo-first-paid-product-pricing-packaging.md`
- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/d2c-action-key-catalog.md`
- `docs/specs/d2c-operator-surface-contract.md`

## Executive decision

Keep the strategic product direction: **Orvo is a sellable Atlassian-like ecommerce operations control plane**, not a Hito/report bot, BI dashboard, chatbot, ERP, or generic automation tool.

Sharpen the first paid product into buyer language:

> **Orvo Control — Tiendanube Exception Desk**: Orvo watches a Tiendanube store, opens evidence-backed operational cases for high-confidence exceptions, sends a concise WhatsApp owner brief, and keeps follow-up state until each issue is acknowledged or resolved.

The internal platform grammar remains Atlassian-like:

```text
connector/run/metric event
→ OperationalCase
→ queue/view
→ workflow state
→ owner/operator brief
→ audited human action
→ resolved or reopened
```

But the sales language should be concrete: **stale data, stuck orders, low/out-of-stock products, fulfillment delays, and owner visibility**.

## ICP and buyer pain

### Best-fit ICP

- Argentine/LatAm physical-goods D2C merchant using Tiendanube/Nuvemshop as a primary commerce source.
- Usually 100-2,000 orders/month, or lower baseline with promo spikes.
- 2-15 person operating team, with owner/founder still involved in daily exceptions.
- Uses WhatsApp for internal/external operations and customer follow-up.
- Tracks exceptions in Tiendanube admin, WhatsApp groups, spreadsheets, carrier portals, ERP exports, or manual screenshots.
- Categories with operational edge cases: apparel, footwear, beauty/cosmetics, accessories, home goods, electronics accessories, supplements, pet, and other SKU/variant/shipping-heavy categories.

### Buyer and champion

- Economic buyer: owner/founder, ecommerce manager, operations lead, or general manager.
- Champions: customer support lead, fulfillment/logistics coordinator, marketplace operator, agency/marketing lead when ads create operational pressure.
- Blockers/approvers: finance/admin for refunds and invoicing, developer/agency for connectors, data/security owner for customer/order information.

### High-intent triggers

1. Upcoming Hot Sale, CyberMonday, Black Friday, Navidad, or brand campaign.
2. Founder asks daily: “¿qué está trabado hoy?” or chases screenshots/status in WhatsApp.
3. Customers repeatedly ask “¿dónde está mi pedido?”
4. Products go out of stock during campaigns or variants create oversell risk.
5. Order counts or statuses disagree across Tiendanube, ERP, shipping, MercadoLibre, Sheets, or WhatsApp.
6. Tiendanube token/webhook/source data fails silently and the team notices too late.
7. Buyer wants team accountability but does not want to buy/configure Jira, Monday, BI, ERP, or a helpdesk.

## Ranked sellable product opportunities

### 1. Tiendanube Operations Exception Desk

**Rank:** 1  
**Primary product area:** Work Management Core + Operator Surfaces  
**Buyer promise:** Know today’s operational exceptions before customers complain: stale data, risky stock, and truth-gated stuck orders, all with evidence and status.

**Why it should lead:**

- It is concrete enough to sell without explaining “control plane.”
- It uses existing repo primitives: `OperationalCase`, run ledger, connector registry, metric registry, operator API/views, WhatsApp owner brief.
- It avoids needing Meta Ads, MercadoLibre, ERP, or a full inbox for first proof.
- It turns reports/metrics into accountable work.

**First case families:**

1. `data_stale` — always included; suppress/narrow downstream claims when Tiendanube data is unsafe.
2. `stockout_risk` — start with out-of-stock, low-stock, and simple “selling and below threshold” flags; avoid forecasting claims.
3. `fulfillment_backlog` — only owner-facing after a store-level truth gate proves payment/fulfillment/status fields are reliable.
4. `sales_drop` — optional and conservative; use only configured floor/trustworthy baseline. Do not lead with it.

**Engineering-ready spec:**

- Add store readiness/truth-gate results to case metadata and/or run summary.
- Ensure `data_stale` can list affected advice/case families.
- Ensure stock cases include product/SKU label, current stock, threshold, source freshness, recent units sold if available, and latest run ID.
- Keep initial executable actions to implemented keys only: currently `acknowledge_case`, `resolve_case`, and `add_comment` appear in `app/brain/operator_api.py`.
- Do not show `pause_promotion`, `refresh_credentials`, `retry_connector`, or `contact_customer` as executable until handlers exist.

**Repo paths:**

- `app/brain/operational_cases.py`
- `app/brain/operator_api.py`
- `app/brain/operator_views.py`
- `app/brain/adapters/tiendanube.py`
- `app/brain/pipeline.py`
- `app/brain/run_ledger.py`
- `app/brain/connector_registry.py`
- `app/brain/reporting.py`
- `app/brain/dispatch.py`
- `scripts/run_orvo_brain_reports.py`
- `tests/test_brain_operational_cases.py`
- `tests/test_operator_case_actions.py`
- `tests/test_operator_case_views.py`
- `tests/test_brain_tiendanube_adapter.py`
- `tests/test_brain_tiendanube_pipeline.py`

### 2. Truth-gated Fulfillment Backlog / Stuck Orders

**Rank:** 2  
**Primary product area:** Work Management Core + Connector Platform  
**Buyer promise:** Find paid/confirmed orders that are aging before fulfillment, with safe evidence and a next action.

**Why it is attractive:**

- It maps directly to customer pain: late orders, WISMO messages, cancellations, and team chasing.
- It makes Orvo feel operational rather than analytical.
- It is easier to prove value in a 30-day Activation Sprint than broad analytics.

**Why it is not automatic first-wave owner-facing:**

- Tiendanube/payment/fulfillment status semantics vary by store.
- Some merchants fulfill outside Tiendanube, batch shipments, allow pickup/preorders, or use ERP/WMS as the true source.
- False positives create support burden and trust loss.

**Engineering-ready spec:**

Create a store readiness scan before enabling owner-facing `fulfillment_backlog`:

```text
checks:
- payment status fields are present and interpretable
- fulfillment/shipping status fields are present and interpretable
- canceled/refunded/unpaid/preorder/pickup/digital exclusions are mapped
- oldest order age can be computed from a stable timestamp
- sample order refs can be redacted safely
- merchant confirms threshold, e.g. 24h/48h/72h
```

Owner-facing case is allowed only if the truth gate passes. Otherwise create `data_stale` or an internal review note.

**Repo paths:**

- `app/brain/adapters/tiendanube.py`
- `app/brain/pipeline.py`
- `app/brain/operational_cases.py`
- `docs/specs/d2c-case-family-catalog.md`
- future focused test: `tests/test_brain_cases_fulfillment_backlog.py`

### 3. Inventory/SKU Mismatch and Low-Stock Operations

**Rank:** 3  
**Primary product area:** Work Management Core + Connector Platform  
**Buyer promise:** Catch low/out-of-stock SKUs and channel mismatches before they create lost sales, oversells, or campaign waste.

**Why it matters:**

- Variants, stockouts, and oversells are common in apparel/beauty/accessories/home goods.
- Inventory risk becomes urgent during campaigns and peak events.
- This can expand later into MercadoLibre/ERP/channel-mix, but Tiendanube-only low-stock is the safer first slice.

**Hard boundary:** Orvo is not an inventory master, WMS, ERP, or replenishment system.

**Engineering-ready spec:**

Start with three deterministic levels:

1. `out_of_stock`: stock equals 0 for enabled product/SKU.
2. `low_stock`: stock is at or below merchant threshold.
3. `low_stock_selling`: stock is low and recent units sold or merchant-important flag indicates actionability.

Suppress if inventory is stale, missing, externally managed, or intentionally hidden; create/update `data_stale` instead.

**Repo paths:**

- `app/brain/adapters/tiendanube.py` (`include_stock=True` path)
- `app/brain/pipeline.py`
- `app/brain/semantics/metric_registry.py`
- `app/brain/operational_cases.py`
- `tests/test_brain_tiendanube_adapter.py`
- `tests/test_brain_operational_cases.py`

### 4. Peak Ops Control Room

**Rank:** 4  
**Primary product area:** Operator Surfaces + Workflow Automation  
**Buyer promise:** For Hot Sale/CyberMonday/brand promos, Orvo gives a daily exception queue and owner WhatsApp brief so operational risk is visible during demand spikes.

**Why it sells:**

- Event urgency shortens sales cycles.
- The buyer already expects operational stress.
- It can be sold as a 30-day Activation Sprint without pretending the product is mature self-serve SaaS.

**Engineering-ready spec:**

- Pre-event readiness checklist: connector health, stock thresholds, stale-data policy, fulfillment truth gate, recipients, quiet hours, max cases in brief.
- During event: daily scheduled brief, optional forced run policy, top case truncation with truthful open-case counts.
- Post-event: proof report: orders monitored, cases opened/updated/resolved, stale-data incidents, stock/fulfillment exceptions, manual checks replaced.

**Repo paths:**

- `scripts/run_orvo_brain_reports.py`
- `app/brain/scheduler.py`
- `app/brain/dispatch.py`
- `app/brain/reporting.py`
- `app/brain/operator_views.py`
- `docs/ops/d2c-pilot-readiness-checklist.md`
- `docs/ops/d2c-pilot-runbook.md`

### 5. Meta Ads-to-Ops Guardrails

**Rank:** 5  
**Primary product area:** Workflow Automation + Connector Platform  
**Buyer promise:** Warn when ad spend keeps running while Tiendanube orders/stock/ops signals say the store cannot convert or fulfill reliably.

**Why it is attractive:** Strong ROI narrative; can justify Growth tier.

**Why it should wait:**

- It risks pulling Orvo into attribution/ROAS debates.
- It requires freshness parity across Meta Ads and Tiendanube.
- False positives create executive panic.

**Engineering-ready spec:**

Allow `spend_without_orders` only when:

- Meta Ads connector and Tiendanube connector both have fresh source state.
- Ad spend is above a merchant-configured minimum threshold.
- Orders/revenue are below configured floor or verified baseline.
- Owner-facing copy states “spend/orders mismatch candidate,” not causal attribution.

**Repo paths:**

- `app/brain/adapters/meta_ads.py`
- `app/brain/adapters/tiendanube.py`
- `app/brain/semantics/metric_registry.py`
- `app/brain/operational_cases.py`
- `tests/test_brain_meta_ads_adapter.py`
- `tests/test_brain_meta_ads_pipeline.py`
- future focused test: `tests/test_brain_cases_spend_without_orders.py`

## Package/SKU hypothesis

### Recommended public ladder

| SKU | Price | Best for | Core promise | Gate |
| --- | ---: | --- | --- | --- |
| **Orvo Control — Activation Sprint** | **USD 149 / 30 days** | First paid proof/design partners | One Tiendanube store, daily WhatsApp exception brief, lightweight case desk, proof report | Paid discovery; not free pilot |
| **Orvo Control Starter** | **USD 99/mo**; USD 79/mo private design partner concession | Owner-led one-store merchants | Daily exception desk for Tiendanube: `data_stale`, `stockout_risk`, safe configured cases | Low support/onboarding burden |
| **Orvo Control Growth** | **USD 199/mo** | Stores with team workflow, higher order/SKU volume, fulfillment or ads complexity | More recipients/checks/history/workflow depth; verified second connector or fulfillment/ads cases | Truth gates passed |
| **Orvo Control Scale** | **USD 399+/mo** | Larger operations, multi-team, multi-store, agency/client complexity | Multi-store or deeper workflows/connectors/audit/support | Scoped implementation |
| **Orvo Platform** | **Custom, usually USD 799-1,500+/mo plus setup** | Merchant/agency needing serious control plane | Custom connectors, APIs/webhooks, security, SLA, advanced permissions | Do not sell before implementation capacity is clear |

### Value metric

Primary value metric: **one monitored Tiendanube store/control plane**.

Secondary limit/upgrade triggers:

- monthly orders monitored,
- active SKUs/products monitored,
- WhatsApp destinations/recipients,
- scheduled check frequency,
- history retention,
- standard connectors,
- workflow depth,
- support/review level.

Do not bill primarily by cases, seats, WhatsApp messages, dashboard views, or AI usage. Cases are proof of value; penalizing case creation discourages the behavior Orvo needs.

### Activation Sprint included scope

- 1 Tiendanube store.
- 1 WhatsApp destination/group.
- Up to 2 owner/operator recipients.
- Daily scheduled exception brief.
- Case queue/history, even if internal/operator-assisted.
- `data_stale` and `stockout_risk` included when data passes readiness.
- `fulfillment_backlog` only if truth gate passes.
- `sales_drop` only if configured floor/baseline is safe.
- Weekly review or async improvement note clearly labeled as pilot support.
- End-of-sprint proof report.

## Product primitives to build next

### Work Management Core

1. Store readiness/truth-gate result model for Tiendanube fields and enabled case families.
2. `OperationalCase` lifecycle expansion only when necessary: current implemented state is `open → acknowledged → resolved`; do not expose unimplemented states as clickable actions.
3. Case metadata fields for affected advice, suppression reason, readiness gate, and confidence/source class.
4. Stable dedupe keys per case family and entity scope.
5. Proof-report aggregation from cases and run ledger.

### Workflow Automation

1. Deterministic rules for create/update/reopen/suppress.
2. Idempotency for repeated daily runs.
3. Dry-run/simulation for case detections before owner-facing enablement.
4. Registered action keys only; no LLM-created actions.
5. Human approval before any external write-back action.

### Connector Platform

1. Tiendanube readiness scan: orders, products/SKUs, stock, status semantics, timestamps/freshness, auth health.
2. Connector health as a first-class source of `data_stale` cases.
3. Capability registry must describe only real execution paths.
4. Redacted diagnostics for auth, rate limit, malformed data, stale state, and missing fields.
5. Certification tests for each owner-facing case input.

### Operator Surfaces

1. WhatsApp exception brief remains a projection of cases, not source of truth.
2. Internal case queue with built-in views for open, acknowledged, resolved, critical, data stale, and stock risk.
3. Case detail with evidence snapshots, run refs, timeline, and safe action keys.
4. Run history/inspection: what ran, what failed/degraded, what was sent/skipped, and which cases changed.
5. Manual actions: acknowledge, resolve, and add comment until more actions are implemented.

### Admin/Security

1. Tenant/business scope on all reads/mutations.
2. Operator actor identity on every mutation.
3. Redaction at API/report/brief/log boundaries.
4. Audit events for case status changes, comments, connector config changes, delivery attempts, and manual runs.
5. Retention/export policy before larger live use.

## Competitor and Atlassian analogy evidence

### Public reference anchors

- Tiendanube app ecosystem: https://www.tiendanube.com/tienda-aplicaciones-nube
- Nuvemshop app ecosystem: https://www.nuvemshop.com.br/loja-aplicativos-nuvem
- CACE ecommerce stats/events: https://cace.org.ar/estadisticas/
- Hot Sale Argentina: https://www.hotsale.com.ar/
- CyberMonday Argentina: https://www.cybermonday.com.ar/
- MercadoLibre seller reputation: https://www.mercadolibre.com.ar/ayuda/reputacion_866
- Jira Service Management requests/issues/queues: https://support.atlassian.com/jira-service-management-cloud/docs/what-are-requests-issues-and-queues/
- Jira workflows: https://support.atlassian.com/jira-cloud-administration/docs/what-are-jira-workflows/
- Jira automation: https://support.atlassian.com/cloud-automation/docs/jira-automation/
- JSM SLAs: https://support.atlassian.com/jira-service-management-cloud/docs/set-up-sla-goals/
- Atlassian audit log: https://support.atlassian.com/organization-administration/docs/view-and-export-the-audit-log/
- Atlassian Marketplace: https://developer.atlassian.com/platform/marketplace/

### Competitor categories and Orvo gap

| Category | Examples | What they do | Orvo gap to exploit |
| --- | --- | --- | --- |
| Ecommerce helpdesk | Gorgias, Zendesk, Intercom, Freshdesk | Conversations, support tickets, macros, AI replies | Orvo starts before the support ticket: operational exceptions across store/fulfillment/inventory/source health |
| WhatsApp commerce/chatbot | Zoko, WATI, Take Blip, Manychat, Botmaker, respond.io | WhatsApp API/inbox/campaign/chat flows | Orvo is the operational case layer; WhatsApp is a projection/notification surface |
| ERP/OMS/back office | Bling, Tiny, Omie, Olist, Linx, TOTVS | Inventory, invoicing, fulfillment records | Orvo wraps around systems of record to coordinate exceptions and follow-up |
| Shipping/tracking | AfterShip, ShipStation, Melhor Envio, Enviopack, Kangu | Labels, tracking, carrier status, notifications | Orvo coordinates what the team does when shipping becomes an operational problem |
| BI/analytics | Triple Whale, Polar Analytics, Looker Studio, Power BI | Dashboards and performance reporting | Orvo turns signals into cases, owners, status, evidence, and resolution |
| Workflow/project tools | Jira, Monday, Asana, Trello, Airtable, Zapier, Make | Generic boards and automations | Orvo ships ecommerce-native cases, connectors, and playbooks instead of blank-canvas setup |

### Atlassian primitive mapping

| Atlassian/JSM primitive | Orvo equivalent | Product area | Wave |
| --- | --- | --- | --- |
| Issue/request | `OperationalCase` | Work Management Core | Now |
| Project | Merchant/store workspace | Work Management Core/Admin | Now |
| Issue type | Case family/type | Work Management Core | Now |
| Workflow/status | Case lifecycle and guarded transitions | Work Management Core | Now, narrow |
| Queue | Built-in operator case views | Operator Surfaces | Now |
| SLA | Case age/response/resolution timers | Work Management Core | Later after cases prove pull |
| Automation | Trigger/condition/action rules over metrics/connectors/cases | Workflow Automation | Later, deterministic only |
| Comments/timeline | Case timeline/evidence/run events | Operator Surfaces | Now |
| Notifications | WhatsApp owner/operator brief | Operator Surfaces | Now |
| Permissions/audit | Tenant-scoped RBAC and audit log | Admin/Security | Incremental |
| Marketplace/apps | Connector/app registry and certification | Connector Platform | Later |
| Assets/CMDB | Commerce object graph: order, SKU, customer, shipment, campaign | Connector Platform | Later; use entity refs now |

## What not to build

### P0 no-build now

1. Generic BI/dashboard product.
2. WhatsApp chatbot, BSP, omnichannel inbox, campaign broadcaster, or FAQ bot.
3. ERP/WMS/inventory/accounting/invoicing replacement.
4. Broad cross-platform ecommerce connector sprawl before Tiendanube proof.
5. Write-back automations that mutate stock, orders, ads, customer messages, refunds, or shipping labels.
6. Full Jira/Zendesk-style case management with boards, custom fields, broad permissions, and workflow builder.
7. Sales-drop/root-cause prediction as flagship positioning.
8. AI copilot language that implies autonomous decisions, predictions, or remediation.

### P1 only after validation

1. Real-time WhatsApp alert firehose; default to daily digest.
2. Assignment, comments beyond implemented `add_comment`, SLA timers, and richer workflow states.
3. Meta Ads `spend_without_orders` and ROAS-adjacent claims.
4. MercadoLibre/channel-mix cases.
5. ERP/shipping/helpdesk connectors.
6. Custom workflow builder.
7. Agency/multi-store console.

## Validation gates

### Gate 1: Store readiness

Before enabling an owner-facing alert type, confirm:

- Tiendanube is the relevant source for that data.
- Auth/API/webhook state is healthy.
- Orders/products/stock fields are present and mapped.
- Status semantics are interpretable.
- Data freshness is inside policy.
- Exclusions are known: canceled/refunded/unpaid/preorder/pickup/digital/external fulfillment.

### Gate 2: Alert precision

Targets for paid pilots:

- At least 80% of delivered exceptions judged useful by the merchant.
- Less than 10-15% “wrong/irrelevant” alerts.
- Default WhatsApp brief shows 3-5 top exceptions, with truthful total open-case count when truncated.

### Gate 3: Actionability

Every case must answer:

1. What happened?
2. Why does Orvo believe it?
3. What evidence/source supports it?
4. What should a human do next?
5. What is the current lifecycle/readiness state: persisted lifecycle (`open`, `acknowledged`, `resolved`) plus any readiness qualifier such as stale, suppressed, or truth-gated?

### Gate 4: Time to value

A new store should see either a useful exception or a useful “data not safe yet” diagnostic within 24-48 hours. If setup requires heavy interpretation, keep it concierge and do not call it self-serve.

### Gate 5: Willingness to pay

Activation Sprint passes when at least 2-3 are true:

- Buyer pays USD 149 or local equivalent for 30 days.
- Brief is read/forwarded/replied to at least 3 times/week.
- At least 3 useful cases are opened/updated and accepted by the buyer.
- Orvo replaces a manual daily check or WhatsApp screenshot chase.
- Buyer asks for more recipients, workflow, checks, history, fulfillment, ads, or another connector.
- Support/onboarding load is compatible with Starter/Growth margin.

## Sales message to use now

Spanish offer:

> **Orvo Control — Sprint de Activación Tiendanube: USD 149 / 30 días.** Conectamos una tienda Tiendanube y te mandamos por WhatsApp un resumen diario de excepciones: datos stale/no confiables, productos con bajo stock o sin stock, y pedidos trabados solo cuando validamos que los estados de pago/despacho son confiables. Cada caso viene con evidencia y seguimiento hasta reconocerlo o resolverlo.

Short positioning:

> Orvo no es otro dashboard ni un bot. Es una cola operativa diaria para Tiendanube: qué necesita atención hoy, por qué, con qué evidencia y qué queda abierto hasta resolverlo.

## Next implementation plan candidates

If this synthesis is accepted, write bite-sized implementation plans for one of these first:

1. **Tiendanube Store Readiness Scan Implementation Plan**
   - Add deterministic readiness diagnostics for products, stock, orders, statuses, timestamps, auth, and freshness.
   - Output readiness to run ledger and suppress unsafe case families.

2. **Stockout Risk Case Hardening Implementation Plan**
   - Add SKU/product-level low/out-of-stock cases with evidence snapshots, dedupe keys, and brief projection.

3. **Fulfillment Backlog Truth Gate Implementation Plan**
   - Backtest and verify payment/fulfillment status semantics before owner-facing cases.

4. **Activation Sprint Proof Report Implementation Plan**
   - Aggregate orders monitored, cases opened/updated/resolved, stale-data incidents, owner actions, and manual checks replaced from run ledger/case store.

5. **WhatsApp Brief Truncation and Case Count Implementation Plan**
   - Ensure brief max-case truncation keeps total open-case count truthful and includes freshness/action context.

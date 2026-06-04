# Competitor analyst — Orvo Tiendanube Exception Desk

Date: 2026-05-25  
Scope: competitor analogy evidence, defensible gaps Orvo can own, pricing/package implications, and distractions not to build for the Tiendanube-first Exception Desk.

## Executive take

Orvo should not enter as BI, dashboard, chatbot, ERP, helpdesk, shipping app, or Zapier clone. The competitive whitespace is a **Tiendanube-first operational exception desk**: deterministic, evidence-backed cases with dedupe, degraded-data honesty, lifecycle/follow-up memory, and WhatsApp/operator projections.

Best external analogy:

> **Jira Service Management / incident queue for ecommerce operations**, packaged for Tiendanube + WhatsApp rather than IT/service teams.

This analogy is more accurate than “AI chatbot” or “analytics dashboard”: the durable object is the case, not the message or chart.

## Evidence base checked

Repo-grounded sources:

- `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/product/tiendanube-exception-desk-opportunity-spec.md`
- `docs/research/2026-05-24-orvo-competitor-landscape.md`
- `docs/research/2026-05-25-product-market-intel-tiendanube-exception-desk.md`
- `docs/gtm/2026-05-25-tiendanube-exception-desk-pricing-packaging.md`

Live page checks via terminal HTTP fetches succeeded for Tiendanube App Store/app pages, Shopify App Store pages, Gorgias, Zendesk, Triple Whale, Polar, Zapier, Zoko, n8n, and selected CRM/app pages. Some pricing pages returned HTTP 403 and should be manually refreshed before quoting externally.

## Competitor analogy matrix

| Category | Evidence observed | What competitor owns | Gap Orvo can own | Pricing/package implication | Do not build |
| --- | --- | --- | --- | --- | --- |
| **Tiendanube apps** | Tiendanube App Store positions apps as ways to “promocionar, vender y gestionar” stores. Gestión page says “Organizá y gestioná tu tienda de forma más eficiente.” Examples fetched: Dux ERP syncs prices/stock/facturación; Producteca integrates channels/ERP/marketplace; BaseLinker advertises 25k+ customers and 1k integrations; Envia handles labels/tracking/notifications; Whatsplaid GPT is a WhatsApp AI chatbot; Alerti automates WhatsApp retention. | Point solutions: ERP-lite, invoicing, shipping, marketplace sync, WhatsApp/chat, reviews, stock alerts, marketing. | Cross-app case coordination: “what needs attention today, why, evidence, who follows up, what remains open.” Orvo sits above apps, not instead of them. | Anchor on one monitored store/control plane, not “another cheap app.” Pilot USD 149 / 30 days and Starter USD 79/mo need a case/follow-up narrative. | App marketplace sprawl, generic app bundle, invoicing/fiscal features, shipping label generation, WhatsApp customer agent. |
| **Shopify ops apps** | Shopify App Store pages: AfterShip = branded order tracking/real-time shipment visibility; ShipStation = shipping across channels/carriers from $14.99/mo; Inventory Planner = demand forecasting/inventory/purchasing; Stocky = inventory management for Shopify POS Pro; MESA = workflow automation from $12/mo. | Mature vertical ops workflows for shipping, tracking, inventory planning, POS, and store automations. | Tiendanube/LatAm focus and owner-level exception queue. Orvo should create cases from ops signals instead of replacing WMS/OMS/inventory-planning products. | Starter should include Tiendanube-only stock/data/sales-floor cases; Growth can add fulfillment depth after field audits. Avoid matching low Shopify app prices because Orvo’s unit is case governance. | Full WMS/OMS, inventory planning optimizer, carrier rate shopping, label printing, broad workflow builder. |
| **Ecommerce helpdesk** | Gorgias pricing page: helpdesk/AI agent for ecommerce, plans by helpdesk tickets: Starter from $10/mo for 50 tickets, Basic from $50/mo for 300, Pro from $300/mo for 2,000, Advanced from $750/mo for 5,000; AI automation priced per resolved conversation. Shopify app says Gorgias resolves support inquiries with automation/AI. Re:amaze from $29/mo; Zendesk pricing page showed per-agent pricing and ticket/omnichannel support. | Customer conversation inbox, ticket routing, macros, AI support, SLA/support agent workflows. | Internal operational cases across Tiendanube stock, sales, stale data, fulfillment, ads, and conversations. Helpdesk ticket != operational case. | Do not price per seat as the main metric. Use one store + order/SKU/recipient/check limits. Unanswered conversations should be later Growth connector, not first SKU. | Support suite, customer inbox, AI replies, help center, SLA-heavy CX platform, ticket macros. |
| **WhatsApp CRMs/chatbots** | Whatsplaid GPT Tiendanube page: “Chatbot con IA para WhatsApp” that attends clients, recommends products, checks order status, and converts conversations. Alerti: WhatsApp revenue retention, abandoned carts, payment reminders, shipping confirmations, reviews, back-in-stock alerts. Zoko pricing page shows WhatsApp/social commerce plans and agent/conversation limits. Kommo positions WhatsApp as sales engine with broadcasts/bots. | Conversational selling/support, broadcast campaigns, chatbot replies, CRM pipelines, abandoned-cart/post-purchase automation. | WhatsApp as projection/habit loop, not product core. Orvo sends case briefs and captures follow-up state from governed `OperationalCase`. | Package includes 1 WhatsApp destination/2 recipients in Starter, more in Growth. Avoid per-message/AI token pricing; use recipients/checks as guardrails. | WhatsApp inbox ingestion in first pilot, outbound customer messaging, chatbot builder, marketing broadcasts, CRM pipeline. |
| **iPaaS / Zapier / Make / n8n** | Zapier page: “No-code automation across 9,000+ apps,” Zaps/Tables/Forms/Agents; Professional starts from $19.99/mo. n8n pricing: unlimited users/workflows/integrations, priced by monthly workflow executions; Starter 20€/mo billed annually. | Plumbing: user-defined triggers, data movement, automations, broad connectors. | Domain judgment: deterministic Tiendanube ecommerce conditions become cases with evidence, dedupe, stale-source suppression, lifecycle, audit. | Do not sell “connect everything.” Sell configured, governed case families. Future automations should be action keys attached to cases with approval/idempotency/audit. | Zapier clone, no-code builder, arbitrary triggers/actions, broad connector chase before case quality. |
| **Analytics / attribution / BI** | Triple Whale page: pricing by GMV, recommended Growth/Pro examples, “real-time command center,” attribution, MMM/MTA/incrementality, 75+ dashboards, Moby AI. Polar pricing: ecommerce semantic layer, BI, incrementality testing, data activations, AI agents, GMV-based plans. Shopify app pages: Polar $750/mo; BeProfit from $49/mo; Lifetimely profit analytics. | Metrics, attribution, dashboards, semantic layer, profitability, marketing reporting. | “Dashboard-to-case conversion”: trustworthy metrics trigger operational cases with follow-up memory. Orvo’s trust moat is evidence and degraded-data honesty, not prettier charts. | Avoid BI anchoring. Starter can be below advanced BI/attribution tools, but should not be sold as cheap reporting. Meta Ads `spend_without_orders` is Growth after Tiendanube freshness is proven. | Attribution/MMM/ROAS suite, custom dashboards, profit analytics, data warehouse, analyst cockpit as launch product. |
| **ERP / inventory / shipping** | Dux Tiendanube: sync stock/prices/facturación, ARCA validation, orders panel, reports. TFactura/Facturante: invoicing/ERP/fiscal workflows. Producteca/BaseLinker: multichannel/ERP/marketplace integrations and stock/price/order sync. Envia: dynamic checkout rates, labels, pickup scheduling, tracking page, notifications. | Administrative/fiscal source of record, stock movements, multichannel sync, shipping execution. | Exception layer above sources of record: stockout risk, stale data, fulfillment backlog only after payment/fulfillment fields are verified. | Keep Custom for ERP/shipping connectors; Starter should not include ERP/accounting/warehouse integration. Growth can add one standard connector only when it unlocks a case family. | Mini-ERP, accounting, tax/fiscal compliance, payment reconciliation, purchasing, POS, warehouse master, shipping operations. |

## Gaps Orvo can own

1. **Case-native ecommerce operations.** `OperationalCase` with type, dedupe key, entity scope, severity, evidence, lifecycle, timeline, and degraded-data caveats.
2. **Tiendanube-first + WhatsApp-first LatAm workflow.** Mature tools are Shopify-first, generic, or app-specific; Orvo can be locally opinionated.
3. **Daily operating queue, not dashboard.** Buyer answer: “qué necesita atención hoy, por qué, qué evidencia lo prueba, y qué sigue abierto.”
4. **Degraded-data honesty.** If Tiendanube data is stale/unsafe, Orvo suppresses/narrows advice and opens `data_stale` instead of inventing.
5. **Cross-system exception orchestration.** Later: ad spend without orders, paid orders aging, unanswered conversations, marketplace channel mix — but only after connector truth gates.
6. **Follow-up memory for small teams.** Existing tools produce alerts/tickets/charts; Orvo remembers operational status, comments/actions, resolved/reopened state.
7. **Action governance.** Later automations should be audited action keys attached to cases, not autonomous black-box edits.

## Recommended competitive positioning

Use:

- “Mesa diaria de casos operativos para Tiendanube.”
- “Tiendanube + WhatsApp primero.”
- “Casos con evidencia, historial y seguimiento.”
- “No es un bot ni otro dashboard.”
- “ERP registra; Orvo prioriza y coordina seguimiento.”
- “Zapier ejecuta reglas; Orvo decide qué condición ecommerce merece un caso.”

Avoid:

- “AI chatbot.”
- “BI dashboard.”
- “ERP replacement.”
- “Zapier for Tiendanube.”
- “Attribution platform.”
- “Automate everything.”
- “Guaranteed revenue lift.”

## Pricing and package implications

1. **Keep store/control-plane billing.** Main value metric: one monitored Tiendanube store/control plane. Seats/messages/events should be guardrails, not core billing.
2. **Pilot remains sensible at USD 149 / 30 days.** It anchors on operational risk caught + manual checking replaced, not on low-cost Tiendanube apps.
3. **Starter at USD 79/mo is plausible but must be narrow.** Include daily brief, one store, one WhatsApp destination, `data_stale`, verified/configured `stockout_risk`, conservative sales-floor case, case history/run health. Do not include ads, ERP connectors, helpdesk ingestion, custom dashboards, or autonomous actions.
4. **Growth at USD 199/mo should be earned by workflow depth.** More recipients/checks/history, weekly review, comments/assignment/timeline when implemented, and Meta Ads `spend_without_orders` only after source freshness parity.
5. **Custom at USD 399+/mo protects complexity.** Use for multi-store, agency portfolio, custom ERP/shipping/marketplace connectors, SLA/security, or nonstandard data cleanup.
6. **If concierge load is high, convert pilots to USD 149/mo continuation before discounting to Starter.** Avoid permanent underpricing if onboarding/operator review is not yet self-serve.
7. **Quote exact competitor prices only after manual refresh.** Some pages are dynamic or blocked; current fetches are directional category anchors, not publish-ready pricing proof.

## Distractions not to build now

- Generic chatbot or “ask your store anything.”
- WhatsApp customer support inbox, chatbot builder, CRM pipeline, or broadcast marketing.
- BI/dashboard/reporting product detached from cases/actions.
- Attribution/MMM/ROAS or profit analytics suite.
- Mini-ERP: accounting, tax, fiscal invoicing, payment reconciliation, purchasing, payroll/HR, POS, warehouse master.
- Shipping app: carrier rates, labels, pickup scheduling, tracking pages, customer notifications.
- Full inventory planner/WMS/OMS.
- Zapier/Make clone, arbitrary no-code automation builder, or broad connector marketplace.
- Autonomous external actions to ads, stock, prices, refunds, orders, customer messages, or Tiendanube edits before approval/audit/idempotency/rollback governance.
- MercadoLibre/channel-mix expansion before Tiendanube-only case truth is proven.
- Broad public web cockpit before core cases, run ledger, evidence inspection, operator API, auth/tenant/audit, and pilot flows are stable.

## Bottom line

Orvo’s most defensible competitor analogy is **an evidence-backed operational case desk for Tiendanube**, not any single app category. Point tools execute work; analytics tools show metrics; helpdesks handle customer tickets; ERPs record facts; iPaaS moves data. Orvo should own the missing layer: **which ecommerce exception matters today, what evidence proves it, what action is next, and what is still unresolved.**

# 2026-06-12 — N2 scout: La Pyme public signals for Orvo

## Scope and sources

Public-only scout. Sources checked: La Pyme homepage and feature pages (`/`, `/funcionalidades/*`, `/integraciones/tiendanube`, `/precios`), public docs index and API v2 OpenAPI (`docs.lapyme.com.ar/llms.txt`, `api-reference/openapi-v2.json`), AI Toolkit/MCP docs, and public social links embedded in the site. No private info, credentials, or unreleased roadmap claims.

## Public feature map

### Positioning and motion
- Public headline frames La Pyme as a **cloud management system for Argentine PyMEs** and a “sistema operativo de tu pyme.”
- Core promise: centralize **ventas, stock, facturación ARCA, tesorería y contabilidad** so local + online operations do not run in separate spreadsheets/screens.
- Strong public demo language: “vendé en todos lados, operá en un solo lugar,” “cada número se puede abrir,” “diseñado para la era de la AI.”
- Onboarding motion: 30-minute demo call, assisted import of products/customers/stock/history, team operating quickly, support from day one.
- Pricing page is explicit: 10-day free trial, no card, monthly/annual promos, tiers by users, deposits, sales/month, integrated accounts, and accounting availability.

### Core modules observed
- **Ventas / facturación:** POS, sales, budgets/remits, credit/debit notes, ARCA e-invoicing A/B/C/E, MiPyME electronic credit invoice, email/ticket printing.
- **Stock / inventory:** multi-deposit, variants, kits/combos, transfers with partial receipt, stock movements, Excel import.
- **Compras:** purchase orders with states, partial/full receipt, supplier invoices, ARCA import, Excel import, stock/cost updates.
- **Tesorería:** cash/banks, own/third-party checks, treasury movements, customer/vendor current accounts.
- **Contabilidad:** chart of accounts, automatic journal entries, daily journal, general ledger, balance sheet, P&L, inflation adjustment, cost centers.
- **Reportes:** real-time dashboards, saved reports, product ranking, channel sales, valued stock, Libro IVA Digital, report builder.
- **Integrations:** Mercado Libre, Tiendanube, Shopify, WooCommerce, ARCA app, API REST, TypeScript SDK.
- **Tiendanube page:** emphasizes one base for stock, prices, orders, customers, and ARCA invoicing; solves overselling, stale prices, duplicate customers, orders outside the operating flow, and delayed fiscal closure.
- **Support / docs / videos:** public site is product-demo and onboarding oriented. Public social link found: X `@lapyme_ar`. No founder-specific public video source was located in the quick public scan; the visible “video” motion is demo/videollamada/product walkthrough, not founder storytelling.

### API / AI / MCP
- Public API page frames the API for external systems, automations, internal tools, webhooks, customer/product/sale/stock flows.
- API v2 OpenAPI inspected: **38 paths / 57 operations** across suppliers, categories, products, warehouses, price lists, purchases, sales, stock transfers, purchase orders, reports, customers, tags, payment methods, POS, and inventory. Auth is bearer API key.
- Docs also expose v1-style pages for more operations: invoices, orders, accounting entries, reports, inventory movements, idempotency, pagination, rate limits, SDK examples.
- AI Toolkit public docs: `npx skills add https://docs.lapyme.com.ar`; public docs MCP at `https://docs.lapyme.com.ar/mcp`; Claude Code/Codex MCP commands are documented.
- Product MCP docs: authenticated MCP at `https://mcp.lapyme.com.ar/mcp`; Claude custom connector flow and Claude Code/Codex commands documented; MCP operates with authorized user permissions.
- Homepage AI examples: assistants connected to Claude/ChatGPT/Grok; ask for month comparisons, stockout detection, purchase order creation; user-level visibility. AI purchase extraction reads supplier invoice PDFs, proposes lines/taxes/totals, then human approves; stock and accounting evidence are generated.

## Copy structurally vs avoid for now

### Copy structurally
1. **One-source-of-truth framing:** ecommerce, POS, stock, fiscal, cash, and reports should feel like one operating loop.
2. **Evidence-first UX:** every metric/case opens to source records, not just generated prose.
3. **AI as an extension surface:** docs, SDK, API, MCP/tooling, examples, and connector docs should make integrators feel safe.
4. **Operational language:** “stock desactualizado,” “precio desfasado,” “pedido fuera del circuito,” “factura pendiente” are concrete pains buyers understand.
5. **Assisted onboarding:** migration/import and “first week operating” matters more than a standalone demo for PyMEs.
6. **Plan clarity:** public pricing and limits reduce friction; Orvo should eventually make pilots/pricing legible.

### Avoid copying now
1. **Do not build an ERP clone.** Accounting depth, ARCA/fiscal correctness, POS, and full ledger behavior are expensive moats/compliance surfaces.
2. **Do not make “Sistema operativo de tu pyme” public copy.** It is too broad and already occupied; use Orvo’s narrower wedge: governed agents for ecommerce operations.
3. **Do not ship generic chatbot positioning.** The value is cases, evidence, and actions, not an assistant that “answers questions.”
4. **Do not let agents write fiscal/accounting records without governance.** Start with readiness checks, exceptions, drafts, and human approval.
5. **Do not claim Tiendanube/WhatsApp coverage before the connector/runtime path is production-ready.**
6. **Do not mention La Pyme/Tango in Orvo landing copy.** Use only as internal competitive signal.

## 10 agent opportunities for Orvo

1. **Tiendanube exception desk:** detect orders stuck, stock mismatches, price mismatches, invoice-not-emitted, dispatch pending, and route to one operator queue.
2. **WhatsApp attention triage:** classify customer messages, summarize order status, draft replies, escalate exceptions, and preserve evidence.
3. **Abandoned/order recovery agent:** identify high-intent carts/messages and propose WhatsApp recovery flows with governed approval.
4. **Stockout/reorder agent:** use sales velocity, current stock, supplier lead times, and variants to propose purchase orders or transfers.
5. **Price/margin guard:** compare channel prices, cost, promotions, FX/import costs, and target margin; propose corrections before selling at bad margin.
6. **ARCA/facturación readiness agent:** check pending invoices, CAE errors, missing customer fiscal data, POS/web-service configuration, and blocked documents.
7. **Treasury collections agent:** detect overdue customer balances, unpaid quotes, bounced/uncleared checks, and draft collection messages.
8. **Purchase invoice intake agent:** extract supplier invoice PDFs, propose lines/taxes/totals, create a review case, and only write after approval.
9. **Daily operator brief agent:** generate a prioritized “12 cases to close today” list with revenue/risk impact and evidence links.
10. **Catalog hygiene agent:** detect duplicate products/customers, missing variants/SKUs, inactive listings, and stale channel mappings.

### Build first: top 3

1. **Ecommerce exception desk for Tiendanube + WhatsApp.** Best wedge: daily pain, clear buyer, measurable hours saved/revenue recovered, and differentiates from generic dashboards.
2. **Stock + price + fiscal readiness agent.** Prevents lost sales and margin leakage; maps directly to D2C operations and can run as read-only checks first.
3. **Daily operator brief / case prioritization.** Makes the product feel like a control plane, not a chatbot; creates a reusable surface for future agents.

## Landing/video ideas for Orvo

- **Hero:** “Controlá tu tienda, stock y WhatsApp desde un panel de casos, no otra planilla.”
- **60-second product video:** Tiendanube order arrives → stock is low → customer asks by WhatsApp → Orvo creates one case → operator approves reply/reorder/invoice → evidence is stored.
- **Before/after:** “Antes: revisar tienda, WhatsApp, stock y facturación en 5 lugares. Después: 12 casos priorizados con evidencia.”
- **Outcome-first landing sections:** “Evitá sobreventas,” “Cerrá facturas pendientes,” “Respondé clientes antes de que se pierda la venta,” “Sabé qué toca hacer hoy.”
- **Operator console demo:** show case cards with severity, source record, suggested action, approval button, and audit trail.
- **Proof metric strip:** stores connected, weekly active operators, cases resolved, hours saved, revenue recovered/influenced, invoice/fiscal errors prevented.
- **Founder/operator POV video:** “Un día operando con Orvo” from morning exceptions to end-of-day close, without naming competitors.

## How Orvo should be better

- **Governed agents:** every agent has scope, permissions, evidence requirements, and approval rules.
- **Operational Cases as source of truth:** chat/WhatsApp summarizes; the case ledger owns state, actions, evidence, and audit.
- **Deterministic detections:** metrics and transitions come from connector/normalizer/metric registry, not LLM improvisation.
- **App-first console:** WhatsApp is for alerts and lightweight approvals; the operator console is the main working surface.
- **Ecommerce wedge:** start with Tiendanube/WhatsApp/D2C exceptions before expanding into full ERP/accounting.
- **Evidence-backed insights:** every recommendation links to orders, stock movements, messages, invoices, payments, or reports.
- **Safe automation:** drafts, confirmations, idempotent actions, and audit logs before any write-back to commerce/fiscal systems.

## Internal positioning note

La Pyme validates that Argentine PyMEs respond to a broad “operating system” narrative, but the public category is already crowded with SaaS/ERP language. Orvo should not compete as “another management system.” Better framing: **governed AI operators for WhatsApp-first commerce**, starting with Tiendanube exceptions and evidence-backed operational cases.

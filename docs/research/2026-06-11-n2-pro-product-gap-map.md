# N2 Pro Product Gap Map: La Pyme/Tango + Agents

Date: 2026-06-11
Author: Hermes / N2 Pro compact research worker
Sources used: `CLAUDE.md`, `docs/research/2026-06-11-lapyme-deep-research.md`, `docs/product/2026-06-11-lapyme-category-mvp-scope.md`, `docs/roadmap/d2c-control-plane-roadmap.md`

## Goal

Map the smallest product gaps Orvo must close so the first sellable slice feels like **La Pyme/Tango category software plus governed agents**, without pretending to be a full ERP clone.

Recommended category line:

```text
Centro operativo con agentes para PyMEs argentinas.
```

The wedge remains Tiendanube/D2C, but the buyer-facing surface should communicate an operating slice: sales/orders, stock/fulfillment, customer attention, ARCA/fiscal readiness, and treasury/reporting readiness.

## Priority definitions

- **NOW MVP** — must be visible in the first paid/concierge pilot to feel like a PyME operating control plane.
- **READYNESS-GATED** — should be visible as status/setup/checklist/work, but must not make owner-facing claims until evidence, freshness, source contracts, and redaction gates pass.
- **LATER** — roadmap/category signal only for now; do not sell or fake in MVP.

## Gap map

| Priority | Gap to close | Why it matters for La Pyme/Tango feel | Orvo treatment |
|---|---|---|---|
| NOW MVP | Operator home / OS snapshot | La Pyme sells an operating system, not a report bot. Orvo needs a serious first screen. | Show module health for Sales, Stock, Customer Attention, ARCA/Fiscal, Treasury/Reporting; open cases; run health; next setup steps; WhatsApp brief preview. |
| NOW MVP | Sales/orders operating truth | Tiendanube/D2C is the wedge and the first source of real evidence. | Keep Tiendanube orders/sales as the automated core. Cases and briefs must cite connector/runtime/evidence refs. |
| NOW MVP | Operational Cases as the main primitive | This is the Orvo differentiation vs generic ERP/dashboard products. | Open/update deterministic cases for `sales_drop`, `stockout_risk`, `data_stale`, `setup_required`, and readiness-gated families. |
| NOW MVP | Module readiness lanes | La Pyme/Tango breadth is buyer-facing; Orvo must show the path without faking depth. | Sales can be live; Stock/WhatsApp/ARCA/Treasury can show setup, stale, or not-ready states with next actions. |
| NOW MVP | Setup-required and stale-data cases | Missing sources must feel like product behavior, not broken reporting. | Create/update `setup_required` and `data_stale` cases when modules cannot prove source truth or freshness. |
| NOW MVP | Evidence and run-health inspection | Agents need trust. Operators must explain every claim. | Surface run ledger, connector status, evidence refs, skipped detections, and redacted degraded-state language. |
| NOW MVP | Redacted owner/operator projections | PyME workflows include PII/fiscal/payment data. | Briefs and console cards must use redacted refs, counts, ages, module status, and action context only. |
| NOW MVP | Agent loop shape | “+ agents” should mean governed monitoring/triage/action preparation, not invented advice. | Agents monitor modules, open/update cases, prepare action recommendations, draft projections, and request setup/access when blocked. |
| NOW MVP | WhatsApp as projection channel | WhatsApp is expected by Argentine PyMEs, but cannot be the source of truth. | Send concise alerts/briefs from cases; canonical state remains Operational Cases/operator console. |
| NOW MVP | Pilot activation checklist | First product is a sellable service slice, not a self-serve feature list. | Checklist: connect Tiendanube, configure thresholds, qualify stock/WhatsApp/ARCA/payment readiness, run daily brief, inspect cases. |

## READYNESS-GATED gaps

| Gap | Gate required before owner-facing automation | MVP treatment |
|---|---|---|
| Stockout risk | Product/catalog/stock source, freshness, thresholds, and redacted evidence refs. | Show as live only when gates pass; otherwise show setup/stale state. |
| Fulfillment backlog | Reliable order status, payment/shipping timestamps, SLA/exclusion rules, resolver ownership, freshness. | Keep in Growth/pilot qualification until gates pass; suppress owner-facing stuck-order claims when ambiguous. |
| Unanswered conversations / WhatsApp attention | Structured inbox/API source, stable conversation refs, last inbound/outbound timestamps, team scope, business hours/SLA. | Show readiness checklist and setup-required cases; no raw message bodies, phone numbers, names, or auto-reply promises. |
| ARCA / facturación readiness | Credential/source status, certificate/AFIP readiness, invoice-flow scope, redaction policy. | Show checklist/status lane first; no full invoice issuance in MVP. |
| Treasury / Mercado Pago readiness | Payment/collection source, reconciliation status, freshness, cash/bank mapping. | Show payment/treasury readiness and unreconciled placeholders; no accounting automation claims. |
| Stock/fulfillment module expansion | Multi-deposit, variants, transfers, movement history, or order-status depth. | Roadmap/readiness copy only until connector evidence supports it. |
| Threshold configuration | Merchant-specific thresholds for sales drops, stockout risk, conversation SLA, stale data. | Make configurable in app/operator console before owner-facing alerts. |
| Operator assignment/resolution workflow | Assignee/ref, timeline, manual comments/actions, deterministic lifecycle. | Needed before WhatsApp projection of customer attention or fulfillment backlog. |
| GTM landing pages | Category pages must match shipped capabilities and readiness gates. | Publish first 8–12 pages only after OS snapshot/case surfaces are credible. |
| Concierge onboarding/service package | La Pyme sells implementation/support; Orvo can win with done-with-you activation. | Package as GAAS/AAS: setup, evidence review, threshold calibration, weekly improvement loop. |

## LATER gaps

| Gap | Reason to defer | Future use |
|---|---|---|
| Full ARCA invoice issuance | High fiscal/accounting risk; needs certified/source contracts. | Post-pilot fiscal automation. |
| Full accounting ledger | Too broad for first MVP and outside D2C wedge. | Later platform/accounting module. |
| Full POS / omnichannel sync | Requires deep channel parity and conflict handling. | Later commerce operations expansion. |
| Mercado Libre, Shopify, WooCommerce parity | Tiendanube is the first wedge; multi-channel should not dilute trust. | Post-pilot channel expansion after source-health model is stable. |
| Full MCP/API assistant product | Useful ecosystem signal, but unsafe as source of truth. | Later governed assistant over cases/evidence. |
| Auto-answering customer messages | High PII/reputation risk and not required for pilot. | Later, with explicit human approval and safe templates. |
| Full custom report builder | La Pyme category signal, but Orvo should be case/action-first. | Later analytics/reporting layer. |
| Full purchase/orders/supplier workflows | Important ERP breadth, but not needed to sell D2C control plane. | Later purchasing/AP module. |
| Multicurrency / wholesale / complex catalog | Argentine relevance exists, but not the first wedge. | Later when commerce source truth is strong. |
| Generic agent marketplace | Risks turning product into generic AI platform. | Later, after Orvo cases/actions are proven. |

## What the first screen should communicate

A merchant should immediately understand:

1. **Qué pasó** — sales/order truth, recent runs, evidence refs.
2. **Qué está roto** — open cases, stale sources, failed connectors.
3. **Qué falta conectar** — readiness for stock, WhatsApp attention, ARCA, treasury.
4. **Qué hago ahora** — prioritized action recommendations from deterministic cases.
5. **Cómo lo comunico** — WhatsApp brief preview sourced from cases.

## Non-negotiables

- Do not fake ERP breadth.
- Do not make WhatsApp the source of truth.
- Do not let LLMs invent metrics, priorities, or lifecycle transitions.
- Do not expose raw secrets, customer messages, phone numbers, fiscal credentials, or payment details.
- Do not promise ARCA issuance, accounting automation, auto-replies, or omnichannel sync in the first MVP.

## Strategic verdict

La Pyme validates the category: Argentine PyMEs will pay for a serious operating system that joins sales, stock, fiscal/admin workflows, reports, and AI over real data. Orvo should not compete by copying La Pyme feature parity. The stronger angle is:

```text
La Pyme/Tango-style operating system + governed operational agents + done-with-you implementation.
```

The first product should feel like a real app/operator console with cases, evidence, module readiness, and concise WhatsApp projections — not a WhatsApp bot, dashboard, or generic AI agent platform.

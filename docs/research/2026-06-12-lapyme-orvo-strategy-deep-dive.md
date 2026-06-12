# La Pyme → Orvo strategy deep dive: integration, agents, content/video plan

Date: 2026-06-12
Author: Claude Fable 5 (strategy research task)
Status: Research synthesis + recommendation
Related:
- `docs/research/2026-06-11-lapyme-deep-research.md` (sitemap/module inventory)
- `docs/research/2026-06-11-lapyme-benchmark.md` (stack/positioning benchmark)
- `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/roadmap/d2c-control-plane-roadmap.md` (Milestone 4C OS snapshot)
- `docs/roadmap/lapyme-competitive-action-plan.md` (2-week action plan from this research)

Internal benchmark only. Do **not** mention La Pyme or Tango in any public Orvo
copy, landing, video, or sales asset unless a comparison page is explicitly
approved later.

## 0. Fresh verification (2026-06-12)

Checked today on top of the 2026-06-11 research:

- Homepage positioning persists: cloud operating/management system for Argentine
  PyMEs; sales, ARCA electronic invoicing, POS, multi-deposit inventory,
  purchases, treasury/accounting, ecommerce integrations.
- Pricing page today: Starter ARS 81,900/mo list (40,950 promo), Pro ARS
  163,900 (81,950 promo), Max ARS 269,900 (134,950 promo), Enterprise custom.
  50% off first 3 months OR 25% off annual (not combinable), prices + IVA,
  10-day free trial without credit card. Extra users ARS 20,000–25,000/mo.
  Plan limits observed today (Pro: 5 users / 3 locations / 2,500 sales; Max: 10
  / 5 / 5,000) are tighter than recorded on 2026-06-11 — they appear to be
  tuning packaging actively.
- **All plans include API access and Claude/ChatGPT connectors.** AI/MCP is a
  bundled capability, not an upsell tier.
- Tiendanube App Store listing exists ("La Pyme ERP", category Gestión):
  unidirectional sync ERP → Tiendanube, **1 review (5.0)** — from ROHI
  Sommiers, the founder's former employer — 5 screenshots, **no video**.
  Support promise: WhatsApp, email, scheduled video calls, humans 8–20h daily.
- Sitemap has no dedicated AI/MCP landing page and no video pages; MCP/AI
  appears inside pricing/API copy. New GTM surfaces: `/partners` and
  `/referidos` (partner + referral programs).
- Founder signal: Tomás Malamud, ~23, UTN Córdoba, ex ROHI Sommiers ecommerce;
  builds in public (stack posts, product clips on X). Press frames La Pyme as
  "a modern, opinionated ERP for SMBs." Their distribution is founder-led
  content + SEO architecture, not marketplace reviews or paid ads.

Net read: La Pyme is real, fast, and category-defining — but its
marketplace/social proof is thin, its sync is one-directional ERP-out, its AI
is an assistant-over-data (not a governed operations layer), and it has no
operational exception/case concept at all. That is the gap Orvo attacks.

## 1. Executive recommendation

**Copy structurally:**

1. **Category language** — "operating system / centro operativo" for Argentine
   PyMEs. Never "chatbot", "dashboard", "reportes".
2. **Module-shaped product anatomy** — the buyer wants to see named modules
   (ventas, stock, atención, ARCA, caja) even if most start as readiness lanes.
   This is exactly Milestone 4C's OS snapshot; accelerate it.
3. **SEO/GTM page architecture** — funcionalidades / soluciones / comparativas
   / guías structure, built gradually around Orvo's wedge.
4. **Onboarding-as-product** — free assisted setup, WhatsApp/video-call human
   support, "done-with-you" implementation. This converts Argentine PyMEs more
   than features do.
5. **Bundled AI access framing** — AI included in every plan, never a "premium
   AI tier".

**Avoid copying:**

1. ERP breadth (accounting ledger, POS, multicurrency, purchases, report
   builder) before sources/readiness gates exist — faking breadth destroys the
   evidence-backed trust position.
2. Public API/MCP as a launch surface before tenant auth, redaction, and audit
   are production-grade.
3. Their stack (Next/Supabase/Vercel rewrite) — copy product shape, keep the
   deterministic Python control plane.
4. Assistant-answers-anything AI framing — Orvo's AI must stay governed:
   deterministic metrics/cases, LLM only for explanation/copy.

**Beat them on:**

1. **Operational Cases / exception desk** — La Pyme records operations; it does
   not detect, prioritize, dedupe, or follow up on what's broken. Orvo's case
   engine (sales_drop, stockout_risk, data_stale today) is a primitive they
   don't have.
2. **Agentic monitoring with auditable evidence** — every owner-facing claim
   carries evidence refs, source freshness, and degraded-data honesty. Their
   assistant can query; ours operates a queue.
3. **WhatsApp-native operating brief** — they use WhatsApp for support; Orvo
   uses it as a governed daily alert/projection channel tied to cases.
4. **Tiendanube-native depth** — they treat Tiendanube as one ERP channel with
   one-way sync; Orvo reads Tiendanube as operational truth and detects
   problems in it.

## 2. Feature map

| La Pyme capability | Buyer pain | Orvo response | Risk if copied too early | Agent opportunity |
|---|---|---|---|---|
| "Sistema operativo de tu pyme" category positioning | Tool sprawl; wants one operating base | **Now** — adopt "centro operativo con agentes" copy + Milestone 4C OS snapshot | Overclaiming breadth we can't evidence | Agents framed as the operating layer, not a bot |
| Sales/orders module (multi-channel) | Manual sales consolidation | **Now** — Tiendanube sales/orders is the implemented core; keep hardening evidence | Low — already real | Revenue-recovery agent triages `sales_drop` |
| Stock multi-deposit, kits, variants, transfers | Stock errors, oversell, manual counts | **Next (thin)** — `stockout_risk` cases + stock readiness lane; no inventory master | Building a stock master without source truth → wrong numbers, dead trust | Stockout sentinel: velocity + threshold cases, restock suggestion via action keys |
| ARCA invoicing A/B/C/E, FCE MiPyME | Invoicing is legally mandatory and painful | **Later issuance; Now readiness** — ARCA readiness lane + checklist cases (`setup_required`) | Issuing fiscal documents wrong is an existential trust/legal risk | ARCA-readiness agent: verifies connection state, explains what's missing; never files |
| Purchases + AI invoice extraction (PDF → lines/taxes) | Manual supplier invoice loading | **Later** — supplier/purchase ingestion after wedge; extraction drafts must be human-approved | OCR/LLM extraction errors silently corrupt costs/stock | Purchase-ingestion agent drafts records from PDFs; deterministic validation + operator approval |
| Treasury: cash/banks/checks, Mercado Pago tied to sales | Reconciliation by spreadsheet | **Next (readiness)** — treasury readiness lane; Mercado Pago source contract first | Claiming reconciliation without bank/MP truth = invented money numbers | Cash/reconciliation readiness agent: flags unreconciled state, never moves money |
| Accounting (entries, ledger, inflation adjustment) | Accountant friction | **Avoid (defer)** — out of wedge per ADR-0005 | Massive scope; competes with accountants' tools; zero wedge value | None for now |
| Accounts current AR/AP, delinquency | Forgotten receivables | **Later** — natural future case family (overdue receivable case) | Needs invoice/payment source truth first | Receivables-chaser agent (post-ARCA/MP data) |
| POS / thermal tickets / barcode | In-person sales | **Avoid** — not D2C wedge | Hardware/UX swamp | None |
| Multicurrency USD | Bi-monetary Argentina | **Avoid (defer)** — display-level later | Accounting-grade FX is deep | None |
| Custom report builder + dashboard | Owners want their numbers | **Avoid** — reports stay projections of cases/metrics | Dashboard-first drifts back into BI positioning ADR-0005 forbids | Brief/projection copy agent (rephrase only, registered claims) |
| Mercado Libre / Shopify / WooCommerce connectors | Multi-channel sellers | **Later** — Mercado Libre after Tiendanube pilot proves | Channel breadth before depth dilutes the wedge | Channel-mix agent only after `channel_mix_shift` promotion gates |
| Tiendanube app (ERP→TN one-way sync) | Easy install/distribution | **Next** — see §3; private connector now, listing later | Marketplace listing with 0 installed proof embarrasses | App listing as distribution for the monitoring agent layer |
| API REST all plans | Integrators/devs | **Later** — internal operator API first (exists); public API post-pilot | Public API = support + security surface too early | API is the future agent/MCP substrate |
| MCP / Claude / ChatGPT connectors all plans | "Ask AI about my business" | **Internally first** — see §3 | Ungoverned MCP can leak tenant data and invent metrics | Orvo-governed MCP: read-only projections of cases/metrics with evidence refs |
| Free migration + implementation + WhatsApp/video human support 8–20h | Fear of switching | **Now** — make the pilot explicitly done-with-you | Cost per pilot rises; fine at pilot scale | Onboarding agent prepares connection checklist, detects setup gaps as cases |
| SEO architecture (funcionalidades/soluciones/comparativas/guías) | Discovery | **Next** — first 8–12 pages mapped to wedge (see 06-11 research §5) | Content ahead of product = vapor | Content drafted from product contracts, human-reviewed |
| Partner + referral programs | Channel distribution | **Later** — agencies are already an identified Orvo channel | Premature partner ops overhead | Agency operator console is a natural partner surface |

## 3. App / Tiendanube / API / MCP strategy

### Tiendanube App Store

**Recommendation: private connector now; public listing as a Phase-2 (post 1–2
paid pilots) milestone.**

- Now: keep onboarding pilots through the existing Tiendanube adapter with
  per-store credentials. No marketplace dependency, no review-queue risk, full
  control of the contract.
- Prepare in parallel (cheap, high option value): register the Tiendanube
  partner/dev account, map app-scopes to the connector registry entry, and
  draft listing copy positioned as **"centro operativo / monitoreo de tu
  tienda"** in the Gestión category — explicitly *not* an ERP, so we don't
  fight La Pyme/iPN ERP head-on in their own listing language.
- Trigger for going public: ≥2 paying pilots + stable OAuth/token-refresh flow
  + OS snapshot console demo-able. A listing with real installs and a product
  video would immediately out-credential La Pyme's 1-review listing.
- Strategic note: La Pyme's sync is **ERP → Tiendanube one-way push**. Orvo's
  read-side monitoring is complementary, not collision — a merchant can run
  both. Don't build write-side sync (price/stock push) for the listing; that
  would drag us into ERP territory and bypass action governance.

### Public API

**Later.** The internal operator API contract exists and is the right surface
to harden. A public API before tenant auth/rate-limits/audit are
production-grade is a security and support liability with zero pilot value.
Revisit after Milestone 4 exit criteria.

### MCP / Claude / ChatGPT exposure

**Internally first; productize after the operator console is real.**

- La Pyme proved the demand signal: "connect your assistant to your business
  data" is now table-stakes language in this category, bundled in every plan.
- But their model (assistant queries the ERP, can create drafts under
  permissions) is exactly the un-governed surface Orvo's contracts forbid if
  done naively.
- Orvo's path:
  1. **Phase 1 (internal, now-ish):** an internal MCP server over the existing
     operator API — read-only projections: case queue, case timeline, run
     history, OS snapshot, registered metrics with evidence refs. Used by us
     for operations/demo. No tenant write access, no raw-row access, secrets
     redacted by the existing redaction contract.
  2. **Phase 2 (pilot upsell):** expose the same read-only MCP to a pilot
     owner's Claude/ChatGPT with tenant-scoped tokens. Marketing line:
     "preguntale a tu asistente qué pasó hoy — y la respuesta sale de
     evidencia, no de inventos." Differentiator vs La Pyme: every answer
     carries evidence/source refs and degraded-data honesty.
  3. **Phase 3 (post-governance):** write actions through MCP limited to the
     registered action keys (`acknowledge_case`, `add_comment`,
     `resolve_case`...), each audited. Never external side effects without
     `request_external_action` approval.
- Hard rule at every phase: MCP is a **projection surface**. It must not
  compute metrics, create cases, or mutate lifecycle outside case/action
  contracts.

## 4. Agent strategy

Agents are packaging + orchestration over the deterministic core. Detection,
metrics, priorities, dedupe, and lifecycle stay deterministic per ADR-0003/
0005. Agents monitor, triage, draft, and route — through registered action
keys only.

### Agents to build for first customers

| Agent | What it does | Deterministic substrate (exists?) | Sellable when |
|---|---|---|---|
| **Revenue recovery** | Watches `sales_drop` cases; drafts the WhatsApp/console brief, suggests `check_storefront`/`review_campaigns`, tracks follow-up to resolution | `sales_drop` owner-facing today | Now |
| **Stockout sentinel** | Watches `stockout_risk`; per-SKU restock/pause-promotion suggestions (`confirm_stock`, `pause_promotion`); reopens on recurrence | `stockout_risk` owner-facing today | Now |
| **Data-truth guardian** | Watches `data_stale`/setup-required; tells the operator exactly which module is blind and how to reconnect (`refresh_credentials`, `retry_connector`) | `data_stale` owner-facing today | Now — this is the honesty differentiator |
| **WhatsApp attention** | Watches `unanswered_conversations` once structured source + SLA/PII/resolver gates pass; routes `reply_pending_chats`; **never answers customers** | Readiness-gated (Milestone 4B) | After source gates; sell as Growth |
| **ARCA readiness** | Walks the merchant through ARCA connection state as checklist cases; reports readiness in OS snapshot; never issues documents | Readiness lane (Milestone 4C) | Pilot+1; readiness only |
| **Cash/reconciliation readiness** | Mercado Pago/treasury source state, unreconciled flags as readiness cases; never touches money | Source contract pending | Pilot+1; readiness only |
| **Supplier/purchase ingestion** | Drafts purchase records from supplier invoice PDFs; deterministic validation; operator approves every record | Not built | Later (post-wedge); first write-side agent candidate |

### Where agents must NOT act

- **No metric/case/priority/lifecycle creation by LLM** — ever (ADR-0005
  invariants).
- **No customer-facing messages** — no auto-replies, coupons, delivery
  promises, refunds (case catalog, family 6).
- **No external side effects** without `request_external_action` + explicit
  approval (action catalog: disabled by default).
- **No fiscal/money actions** — ARCA filing, payments, reconciliation entries
  remain human/deterministic-only indefinitely.
- **No invented action keys** — copy layers rephrase registered actions only.
- **No claims from stale sources** — degraded data suppresses or narrows
  advice; the agent says so.

This is the positioning sentence vs La Pyme's assistant: *their AI answers
questions; Orvo's agents run an audited operations queue.* (Internal phrasing
only — publicly we just describe Orvo.)

## 5. Landing / video strategy

La Pyme's site today has **no embedded product videos**; their video presence
is founder build-in-public clips on X. The bar is low and the opportunity is
real: short, honest, screen-real videos make an "operating system" claim
tangible faster than copy.

### Asset rules (no fake footage)

- Record only real product surfaces: operator console/OS snapshot, real
  WhatsApp briefs, run history, case timelines — on a **demo tenant with
  redacted/synthetic data** clearly labeled as demo data.
- Never show metrics, modules, or automations that aren't implemented; for
  readiness lanes, show them honestly as "por conectar" — that honesty is the
  product.
- No secrets/tokens/URLs on screen; review every frame against the redaction
  rules before publishing.
- Spanish (Argentina), subtitled, 16:9 for landing + 9:16 cuts for social.
- No mention of La Pyme/Tango/competitors.

### Video scripts/storyboards

**V1 — Founder explainer: "Tu pyme tiene un centro operativo" (60–90s)**
- Placement: landing hero + X/LinkedIn.
- Storyboard: (1) founder to camera: "Cada mañana revisás Tiendanube,
  WhatsApp, el stock, la plata — todo a mano." (2) cut to console: "Orvo mira
  eso por vos y te muestra qué necesita atención, con evidencia." (3) one real
  case walkthrough (stockout) ending in a WhatsApp brief. (4) close: "No es un
  dashboard ni un chatbot. Es tu centro operativo." CTA: pilot.

**V2 — Product walkthrough: the OS snapshot (2–3 min)**
- Placement: landing "cómo funciona" section + sales-call pre-send.
- Storyboard: screen capture, voiceover. Open the operator console → module
  health (Ventas ok / Stock ok / Atención por conectar / ARCA por conectar /
  Caja por conectar) → open case queue → one case timeline with evidence refs
  → run history showing a degraded connector handled honestly → the WhatsApp
  brief that resulted. Beat to land: "cada número tiene una fuente".

**V3 — Operational case demo: "Riesgo de stock detectado" (60s)**
- Placement: landing case-study strip + social cut + onboarding.
- Storyboard: morning WhatsApp brief arrives ("Campera X: 3 unidades, vendió 8
  en 7 días — fuente: Tiendanube") → operator opens the case in console →
  confirms stock, marks in progress, resolves → next day's brief references
  the resolved state instead of re-alerting. Beat: follow-up memory, not alert
  spam.

**V4 — Before/after PyME workflow (90s)**
- Placement: sales calls + landing secondary.
- Storyboard: split screen. Before: owner with 6 tabs, spreadsheet, scrolling
  chats, "¿vendimos bien ayer? ni idea". After: one console + one daily
  WhatsApp brief; owner acts on 2 cases and closes the laptop. Voiceover
  quantifies honestly: "menos revisión manual, cero números inventados". Use
  staged-but-labeled reenactment for the "before" only; all "after" footage is
  real product.

**V5 — Tiendanube + WhatsApp case: "Tu tienda te avisa" (60s)**
- Placement: onboarding + Tiendanube app listing (when public) + social.
- Storyboard: connect Tiendanube (real OAuth flow, token blurred) → first run
  in run history → first OS snapshot appears → that evening's WhatsApp brief
  with a real `sales_drop` evidence line and a degraded `data_stale` caveat
  for an unconnected module. Beat: "instalás, conectás, y empieza a operar —
  y te dice qué falta conectar."

### Placement map

| Surface | Videos |
|---|---|
| Landing | V1 (hero), V2 (how it works), V3 (case strip) |
| Sales calls | V2 (pre-send), V4 (objection: "¿otro dashboard?") |
| Onboarding | V5 (activation), V3 (how to work a case) |
| Social/X founder channel | V1 + 9:16 cuts of V3/V5; build-in-public clips of real console progress |

Production order: V2 first (forces the console to be demo-able — it is the
Milestone 4C forcing function), then V3, V1, V5, V4.

## 6. Wedge prioritization

### 3 must-build slices (next 2 weeks)

1. **OS snapshot / operator home (Milestone 4C core):** module health for
   Ventas, Stock, Atención, ARCA, Caja derived from connector/runtime/case
   state, with setup-required cases for unconnected lanes. This single surface
   moves Orvo from "report tool" to "operating system slice" — and makes V2
   recordable.
2. **Console-projected case queue + timeline polish over the three live
   families** (`sales_drop`, `stockout_risk`, `data_stale`): operator can
   open, acknowledge, comment, resolve; next brief reflects state. The
   follow-up loop is the demo moment no ERP has.
3. **Pilot activation path hardening:** Tiendanube connect → first run → first
   OS snapshot → first WhatsApp brief, with the pilot-readiness checklist and
   redacted demo tenant for videos/sales.

### 3 differentiators to prove (vs the La Pyme benchmark, internally)

1. **Exception desk:** Orvo detects/dedupes/follows up on problems; an ERP
   records transactions. Proof: a week of briefs where repeated issues update
   one case instead of spamming.
2. **Evidence + degraded-data honesty:** every owner-facing number carries a
   source line; stale sources visibly narrow advice. Proof: V2/V5 footage of a
   degraded run handled honestly.
3. **Governed agent layer:** agents draft and route through registered action
   keys with audit trails — not a Q&A assistant. Proof: case timeline showing
   agent-suggested action → operator approval → resolution.

### 3 features to explicitly defer

1. **Full ARCA invoicing issuance** (readiness lane only; no fiscal documents).
2. **Accounting / treasury ledgers and reconciliation writes** (readiness
   lanes; Mercado Pago source contract first).
3. **Public API/MCP + Tiendanube public listing + Mercado Libre connector**
   (prepare quietly; ship after paid-pilot proof).

## 7. Pricing / pilot recommendation

Public signal: Argentine PyMEs pay ARS 81,900–269,900/mo list (+IVA) for an
operating system that bundles painful local workflows, with 50%-off-3-months
promos, ~25% annual discount, per-user expansion fees, free
migration/implementation, and a 10-day no-card trial.

Recommendation:

- **Keep the USD 149 paid pilot** (existing close kit) as the entry: 30-day
  done-with-you activation, Tiendanube + WhatsApp brief + console access.
  USD 149 ≈ the promo band of the benchmark's mid plans — credible, not cheap.
- **Post-pilot subscription hypothesis:** ARS 90k–160k/mo (+IVA) "Centro
  Operativo" plan once the OS snapshot console is real; Growth tier ARS
  180k–260k adding readiness-gated modules (WhatsApp attention, fulfillment)
  as they pass gates. Anchor on operational value ("detección + seguimiento +
  evidencia"), not on module count we can't match.
- **Copy their commercial mechanics, not their price points:** included
  implementation/migration-style onboarding, human WhatsApp support window,
  annual discount, and AI/agents bundled in every tier (never an "AI add-on").
- **Do not** launch a self-serve free trial yet — pilot capacity is the
  constraint and done-with-you is the differentiator at this stage.

## 8. Risks and anti-copy rules

### Risks

1. **Category-breadth trap:** chasing ERP module parity stalls the wedge and
   forces fake/readiness-less surfaces. Mitigation: readiness lanes + ADR-0005
   out-of-scope list are binding.
2. **Speed asymmetry:** a solo founder on a modern stack ships visible
   features weekly. Mitigation: compete on the case/evidence/agent primitive
   they don't have, not on feature velocity.
3. **AI-table-stakes compression:** "connect Claude to your business" is now
   bundled, cheap positioning. Mitigation: sell governed agents + audited
   operations, demo evidence refs.
4. **Marketplace squeeze:** if Tiendanube deepens native analytics/alerts or
   La Pyme adds detection-like features, the read-only wedge narrows.
   Mitigation: follow-up/case memory + WhatsApp operating loop are workflow
   lock-in, not just detection.
5. **Pricing fog:** ARS list prices move with promos/inflation; revalidate
   before any pricing decision (their plan limits already shifted between
   06-11 and 06-12).
6. **Video overclaim risk:** demo videos drift into showing aspiration as
   product. Mitigation: asset rules in §5; every frame maps to implemented
   capability or labeled readiness state.

### Anti-copy rules (binding for workers and content)

1. Never mention La Pyme/Tango (or their founder) in public Orvo surfaces,
   metadata, filenames, or sales decks without explicit approval.
2. Never copy their copy: write Orvo claims from Orvo contracts
   (PRD/catalogs), not from their pages.
3. Never fake module breadth: unconnected modules render as honest readiness
   lanes, not as features.
4. Never bypass platform contracts to match a benchmark feature quickly
   (ADR-0005 invariants; worker addendum stop rules).
5. Never replicate their assistant model: no LLM with raw data access creating
   records; Orvo AI stays on projection/explanation surfaces with registered
   action keys.
6. Never adopt their stack as a strategy: stack choices follow Orvo's runtime
   needs, not benchmark mimicry.
7. Never commit scraped private/authenticated content; public pages only, and
   keep this doc internal.

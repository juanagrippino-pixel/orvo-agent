# Product & Market Intelligence — Tiendanube Exception Desk

Date: 2026-05-25  
Owner: Product & Market Intelligence  
Scope: Convert the Orvo pivot into a sellable first product, SKU hypothesis, product primitives, and engineering-ready specs.

Related:
- `docs/product/tiendanube-exception-desk-opportunity-spec.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/research/2026-05-25-ecommerce-ops-buyer-research-tiendanube.md`
- `docs/gtm/2026-05-25-tiendanube-exception-desk-pricing-packaging.md`
- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/d2c-action-key-catalog.md`
- `docs/specs/d2c-operator-surface-contract.md`

## Executive decision

The first product people are most likely to pay for is:

> **Orvo Tiendanube Exception Desk** — a daily case desk for Tiendanube stores that opens, dedupes, and tracks evidence-backed operational cases, then projects the queue into WhatsApp and internal operator surfaces.

Buyer-facing phrasing:

> **No es un bot ni otro dashboard. Orvo abre casos operativos con evidencia de Tiendanube y seguimiento por WhatsApp.**

The launch promise should stay narrow and truth-gated:

1. `data_stale` when Tiendanube/source data is unsafe, stale, unauthorized, malformed, or failed.
2. `stockout_risk` for configured/moving/important products once SKU/product stock evidence is fresh and mapped.
3. `sales_drop` only as **ventas bajo piso configurado** or with a trustworthy baseline; never broad AI anomaly/root-cause detection.
4. `fulfillment_backlog` remains conditional: owner-facing only if real Tiendanube order/payment/fulfillment fields prove reliable for that store; otherwise say **pedidos pendientes en Tiendanube** only as operator-assisted/internal review.

The internal architecture remains the Atlassian-like control plane: connector registry, compiled runtime, run ledger, metric/evidence registry, `OperationalCase`, lifecycle, timeline, action keys, redaction, and operator APIs.

## Repo grounding from this run

Current implementation supports the strategic direction but is not yet safe for the full sales claim:

- `app/brain/operational_cases.py` defines `OperationalCaseStatus = Literal["open", "acknowledged", "resolved"]`; richer statuses such as `in_progress` and `dismissed` are still future workflow depth.
- `OperationalCaseType` currently includes `sales_drop`, `stockout_risk`, `spend_without_orders`, `data_stale`, `unanswered_conversations`, and `channel_mix_shift`; it does **not** yet include `fulfillment_backlog`.
- Current report-derived case detection still maps from insight titles (`"stock"`, `"ventas"`, `"conversaciones"`, etc.) and uses broad stockout dedupe: `stockout_risk/business/monitored/commerce.inventory/daily`.
- The D2C case catalog specifies SKU-level stockout dedupe: `<business_id>/stockout_risk/sku/<sku_or_product_id>/commerce.inventory/daily`.
- `data_stale` has a catalog-backed detection helper, and failed/forced runtime paths already test opening `data_stale` cases.
- Operator queue/query surfaces exist (`app/brain/operator_views.py`, `app/brain/operator_api.py`) with built-in `open_cases`, `critical_open`, `data_stale`, and `stockout_risk` views.

Implication: sell the pilot as **operator-assisted, evidence-backed exception monitoring**, not fully self-serve automation, until SKU-level stockout evidence/dedupe and pending-order truth are implemented.

## ICP and buyer pain

### Primary ICP

- Argentine/LatAm physical-goods D2C store where Tiendanube is the main storefront or a key operational source.
- Buyer/champion: founder-owner, ecommerce operator, or small team lead responsible for daily sales, stock, dispatch, and customer escalation.
- WhatsApp is already an operating surface for screenshots, status requests, and follow-up.
- Store has enough operational volume that missed exceptions cost time, customer trust, stock availability, or ad/agency accountability.

### Best early fit signals

- Owner asks staff/agency for daily screenshots or status updates.
- Store has many SKUs/variants and active promotions.
- Recent stockout, oversell, stale stock, or paid orders stuck before dispatch.
- Tiendanube data is maintained well enough to support deterministic detection.
- Buyer wants evidence and follow-up history, not “AI magic.”
- Buyer can name one operational miss in the last 30–60 days that would have paid for the pilot.

### Poor fit signals

- Low-volume hobby store or digital/service business with little stock/fulfillment pain.
- Tiendanube stock/order data is known to be wrong and no one will fix source data.
- Buyer wants dashboards, reports, chatbot, guaranteed revenue lift, or autonomous edits to ads/stock/orders.
- No accountable human owns case follow-up.

## Ranked sellable product opportunities

| Rank | Opportunity | Buyer promise | Build next? | Notes |
| ---: | --- | --- | --- | --- |
| 1 | Tiendanube daily exception desk | “Qué necesita atención hoy, por qué, con evidencia, y qué sigue abierto.” | Yes | Package-level promise; cases are the product, WhatsApp is projection. |
| 2 | SKU-level stockout risk | “No te quedes sin stock en productos que se están vendiendo.” | Yes | Must use SKU/product dedupe and fresh inventory evidence. |
| 3 | Data stale / unsafe advice | “Si una fuente no está confiable, Orvo te lo dice y no inventa.” | Yes | Trust moat; must suppress/narrow stock/sales/order advice. |
| 4 | Pending paid orders / fulfillment backlog | “Revisá pedidos pendientes cuando los estados de pago/despacho estén verificados.” | Conditional/internal | Build only after real Tiendanube fields prove `paid` + `unfulfilled` + aging semantics and an owner-facing projection gate exists. |
| 5 | Sales below configured floor | “Ventas bajo el piso configurado; revisá tienda/pagos/tráfico.” | Secondary | Useful but noisy; never pitch broad anomaly/root cause. |
| 6 | Meta Ads spend without orders | “Se está gastando y no entran pedidos.” | Later Growth | Strong ROI story after Meta Ads + Tiendanube freshness parity. |
| 7 | Unanswered WhatsApp/support conversations | “Chats de venta/soporte esperando demasiado.” | Later | Valuable but connector/privacy/provider complexity is not first-wedge safe. |
| 8 | Channel mix / MercadoLibre expansion | “Cambió dónde se están vendiendo los productos.” | Later Custom/Growth | Defer until Tiendanube-only wedge is trustworthy. |

## Sellable package / SKU hypothesis

Use store/control-plane billing, not per-seat billing.

| SKU | Buyer-facing name | Price hypothesis | Included | Hard exclusions |
| --- | --- | --- | --- | --- |
| Pilot | **Piloto Exception Desk Tiendanube + WhatsApp** | USD 149 / 30 days or ARS equivalent at invoice time | 1 store, 1 WhatsApp destination, daily case brief, assisted setup/import, configured thresholds, internal/operator-assisted case history, weekly review | Meta Ads, MercadoLibre, custom connectors, WhatsApp inbox ingestion, autonomous actions, guaranteed ROI |
| Starter | **Orvo Exception Desk Starter** | USD 79/mo after pilot | Daily Tiendanube exception desk, case queue/history, `data_stale`, verified/configured `stockout_risk`, conservative sales-floor case, 90-day case/run history; pending-order case only after field audit | Full BI, ERP, unlimited checks/SKUs/recipients, ads connector, helpdesk, default fulfillment promise |
| Growth | **Orvo Exception Desk Growth** | USD 199/mo | Future workflow depth after implementation: comments, assignment, richer status/timeline, more recipients/checks, higher SKU/order limits, weekly review, future Meta Ads case when verified | Publish only after base wedge converts; do not lead with Growth. |
| Custom | **Orvo Operations Control Plane Custom** | USD 399+/mo scoped | Multi-store, custom connector, agency portfolio, formal SLA/security, multi-channel | Do not use Custom to distort Starter roadmap. |

Skeptical pricing adjustment: keep USD 79/mo as the self-serve Starter hypothesis, but for concierge-heavy early customers consider converting Pilot directly to **USD 149/mo same-scope continuation** until onboarding/support load is measured.

## Competitor / Atlassian analogy evidence

### External evidence checked this run

HTTP reachability was verified for:

- Tiendanube App Store: https://www.tiendanube.com/tienda-aplicaciones-nube
- Tiendanube plans/pricing page: https://www.tiendanube.com/planes-y-precios
- Tiendanube WhatsApp selling guide: https://www.tiendanube.com/blog/como-vender-por-whatsapp/
- WhatsApp Business Platform: https://whatsappbusiness.com/products/business-platform/
- Gorgias pricing: https://www.gorgias.com/pricing
- Zapier pricing: https://zapier.com/pricing
- Triple Whale pricing: https://www.triplewhale.com/pricing

Make pricing returned HTTP 403 in the terminal check, so verify manually before quoting: https://www.make.com/en/pricing

### Competitive positioning

- Tiendanube apps solve point jobs: ERP-lite, shipping, invoicing, marketplace sync, WhatsApp/chat, reviews, and alerts. Orvo should coordinate exceptions above them, not replace them.
- ERPs own records, stock movements, fiscal workflows, and accounting. Orvo should not become the financial source of truth.
- Shipping/fulfillment tools execute delivery workflows. Orvo can open a pending-order/fulfillment case only when evidence is reliable.
- Helpdesks and WhatsApp CRMs own customer conversations. Orvo can later ingest unanswered conversations as a case signal; it should not become an inbox now.
- BI/analytics tools show metrics. Orvo opens cases with lifecycle, evidence, and follow-up.
- iPaaS tools execute user-configured rules. Orvo decides which ecommerce conditions deserve a governed case/action.

### Atlassian primitive mapping

Copy the durable mechanics, not the breadth:

| Atlassian primitive | Orvo primitive | Launch stance |
| --- | --- | --- |
| Jira issue/work item | `OperationalCase` | Core sellable object. |
| Issue types/custom fields | D2C case families + typed evidence schemas | Use controlled schemas; no arbitrary custom fields. |
| Workflow statuses/transitions | deterministic lifecycle + transition audit | Fixed family workflows first. |
| Queues/saved filters/JQL | operator queues and built-in views | Built-ins before writable saved views. |
| Activity timeline | evidence + run + comment + action timeline | Trust layer. |
| Jira Automation | trigger/condition/action rules | Narrow, dry-run, audited, allowlisted. |
| Marketplace/Forge/Connect | connector registry + certification | Internal registry first; public marketplace later. |
| Admin/Guard | tenant scope, auth, redaction, audit | Required before operator/customer scale. |
| JSM SLAs | connector freshness and unresolved critical-case timers | Sell freshness honesty before broad SLA. |

## Engineering-ready specs

### Spec A — SKU-level `stockout_risk`

**Product area:** Work Management Core + Operator Surfaces  
**Repo paths:** `app/brain/operational_cases.py`, future/additive `app/brain/d2c_case_policies.py`, `tests/test_brain_operational_cases.py`, `tests/test_operator_case_views.py`

**Detection:** open/update when SKU/product stock is at or below configured threshold and either recent units sold > 0 or SKU is explicitly marked important, with fresh Tiendanube inventory data.

**Suppress:** stale/missing inventory, missing SKU/product ID, non-moving SKU without strategic flag.

**Dedupe:** `<business_id>/stockout_risk/sku/<sku_or_product_id>/commerce.inventory/daily`.

**Evidence:** SKU/product ID, label, stock units, threshold, recent sales/window, freshness state, connector/run/artifact refs.

**Implemented operator actions today:** `acknowledge_case`, `resolve_case`. **Operator-assisted recommendations/catalog keys, not implemented handlers yet:** `confirm_stock`, `pause_promotion`, `add_comment`. `mark_in_progress` and `dismiss_case` remain Growth/workflow roadmap until lifecycle states exist in code.

**Acceptance:** two different SKUs create two cases; repeated runs for same SKU update one case; stale stock data creates/updates `data_stale` and does not open stockout.

### Spec B — `data_stale` gating

**Product area:** Connector Platform + Admin/Security + Work Management Core  
**Repo paths:** `app/brain/operational_cases.py`, `app/brain/runtime.py`, `app/brain/run_ledger.py`, `tests/test_brain_operational_cases.py`, `tests/test_run_orvo_brain_reports_script.py`

**Detection:** open/update when Tiendanube credentials fail, rate limits block safe execution, source freshness exceeds policy, malformed responses prevent safe metrics, or required fields are unavailable.

**Effect:** suppress or narrow downstream `stockout_risk`, `sales_drop`, and pending-order advice.

**Dedupe:** `<business_id>/data_stale/connector/<connector_type>/runtime.freshness/daily`.

**Evidence:** connector type, failure class, stale duration, latest run ID, last success if known, affected case families.

**Implemented operator actions today:** `acknowledge_case`, `resolve_case` only after successful freshness recovery. **Operator-assisted recommendations/catalog keys, not implemented handlers yet:** `refresh_credentials`, `retry_connector`, `add_comment`.

**Acceptance:** no owner-facing brief claims inventory/sales/order facts from stale Tiendanube data.

### Spec C — `fulfillment_backlog` / pending-order truth gate

**Product area:** Work Management Core + Connector Platform  
**Repo paths:** `app/brain/adapters/tiendanube.py`, `app/brain/operational_cases.py`, `docs/specs/d2c-case-family-catalog.md`, `tests/test_brain_tiendanube_adapter.py`, future `tests/test_brain_cases_fulfillment.py`

**Decision gate:** do not make this owner-facing until real Tiendanube data proves Orvo can distinguish paid/unfulfilled/aging orders with enough reliability **and** `execution_ledger._owner_brief_cases()` or its successor has an explicit owner-facing visibility allowlist/readiness gate.

**Detection if gate passes:** open/update when paid/unfulfilled order count >= threshold or oldest paid/unfulfilled age >= configured SLA.

**Adapter truth contract before owner-facing release:** normalize real Tiendanube payloads into `is_paid`, `is_unfulfilled`, `is_cancelled_or_refunded`, `pending_since`, `age_hours`, `field_confidence`, and redacted sample order refs. Suppress when payment status, fulfillment/shipping status, timestamps, timezone, cancellation/refund/test-order status, or external ERP/carrier source-of-truth boundaries are missing or ambiguous.

**Suppress:** missing/ambiguous payment or fulfillment status, stale order source, shipping/ERP state required but unavailable.

**Dedupe:** `<business_id>/fulfillment_backlog/channel/tiendanube/commerce.fulfillment/daily`.

**Evidence:** affected count, oldest age, safe/redacted order refs, payment/fulfillment grouping, source freshness, run ID.

**Implemented operator actions today:** `acknowledge_case`, `resolve_case`. **Operator-assisted recommendations/catalog keys, not implemented handlers yet:** `inspect_pending_orders`, `assign_owner`, `add_comment`. `mark_in_progress` and `dismiss_case` remain Growth/workflow roadmap until lifecycle states exist in code.

**Acceptance:** internal-only fulfillment cases are stored but excluded from owner WhatsApp briefs unless `owner_facing_ready == true`, `field_confidence == "verified"`, source freshness is safe, and redacted evidence snapshots exist. Backtest at least 2-3 real/sandbox stores and compare Orvo pending-order count/oldest age against operator review before publishing the claim.

## What not to build now

- Generic chatbot or “ask your store anything.”
- Dashboard-first UI detached from cases/actions.
- Full ERP/accounting/WMS/payment reconciliation.
- WhatsApp helpdesk/inbox automation.
- Attribution/MMM/ROAS suite.
- Zapier/Make clone or broad no-code automation builder.
- Public marketplace/developer SDK.
- Autonomous external actions to ads, stock, prices, refunds, orders, or customer messages.
- Broad Growth tier claims before the Tiendanube exception desk converts.

## Next 7-day validation actions

1. Narrow the external offer to **Mesa diaria de casos operativos para Tiendanube**.
2. Build a target list of 50 Tiendanube physical-goods stores with visible SKU complexity and WhatsApp-heavy operations.
3. Run 10–20 problem interviews focused on stockouts, paid orders stuck, stale data, and daily manual checks.
4. Ask for 3 paid pilots at USD 149 / 30 days or local equivalent.
5. Run a technical truth audit on real/sandbox Tiendanube data: orders, products, variants/SKUs, stock, payment/fulfillment statuses, freshness, OAuth/scopes/rate limits.
6. Backtest 30 days of Tiendanube data for 2–3 stores and measure actionable cases/week and false positives.
7. Build only the missing technical gates: owner-facing projection allowlist, SKU-level stockout evidence/dedupe, robust stale-data suppression, and operator inspection before broader connectors or dashboards.

# Product & Market Intelligence — Control Plane Synthesis Run

Date: 2026-05-25 15:45 UTC  
Owner: Product & Market Intelligence  
Scope: Convert current Orvo pivot into paid ICP, SKU hypothesis, ranked product primitives, and engineering-ready next specs.

Related repo sources:
- `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/product/tiendanube-exception-desk-opportunity-spec.md`
- `docs/gtm/2026-05-25-orvo-first-paid-product-pricing-packaging.md`
- `docs/gtm/2026-05-25-tiendanube-exception-desk-pricing-packaging.md`
- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/d2c-action-key-catalog.md`
- `docs/specs/d2c-operator-surface-contract.md`
- `docs/plans/2026-05-25-tiendanube-exception-desk-technical-truth-gates.md`

---

## Executive recommendation

The first product people are most likely to pay for remains:

> **Orvo Tiendanube Exception Desk** — one monitored Tiendanube store/control plane that opens evidence-backed operational cases, keeps lifecycle/follow-up state, and projects the daily exception queue into WhatsApp and internal operator surfaces.

The sellable promise should be narrower than “AI control plane” and sharper than “daily report”:

> **No es un chatbot ni otro dashboard. Orvo abre casos operativos con evidencia de Tiendanube, te dice qué necesita atención hoy y mantiene qué sigue abierto/resuelto.**

Charge only as an assisted, truth-gated pilot until SKU-level stockout evidence/dedupe, stale-data suppression, and an owner-facing brief projection allowlist/readiness gate are fully landed:

- **Pilot:** USD 149 / 30 days, 1 Tiendanube store, 1 WhatsApp destination, assisted setup, daily exception brief, weekly review.
- **Starter:** USD 79/mo design-partner / USD 99/mo public target once onboarding COGS are known.
- **Growth:** USD 199/mo only when workflow depth, more recipients/checks, weekly review, or a second verified connector is needed.
- **Custom:** USD 399+/mo scoped for multi-store, custom connectors, agency/portfolio, SLA/security, or managed-service expectations.

Do not sell dashboards, chatbot automation, ERP replacement, generic AI, attribution/ROAS, autonomous external actions, or self-serve setup before the implementation can support those claims.

---

## Repo grounding from this run

Current code supports the control-plane direction, but the live claim must be constrained:

- `app/brain/operational_cases.py` currently defines `OperationalCaseStatus = Literal["open", "acknowledged", "resolved"]`; `in_progress`, `dismissed`, assignment, and richer workflow states are not code-supported statuses yet.
- `OperationalCaseType` currently includes `sales_drop`, `stockout_risk`, `spend_without_orders`, `data_stale`, `unanswered_conversations`, and `channel_mix_shift`; it does **not** include `fulfillment_backlog` as a first-class case type yet.
- `app/brain/operator_api.py` currently allowlists `acknowledge_case`, `resolve_case`, and `add_comment`; do not expose `assign_owner`, `mark_in_progress`, `dismiss_case`, or external action buttons until handlers, lifecycle states, timeline events, and tests exist.
- `app/brain/operator_views.py` already has built-in case views including `open_cases`, `critical_open`, `data_stale`, and `stockout_risk`; these are good internal operator-surface primitives for pilot operations.
- Existing tests still include broad report-derived stockout dedupe examples such as `stockout_risk/business/monitored/commerce.inventory/daily`; the product catalog target is SKU-level dedupe: `<business_id>/stockout_risk/sku/<sku_or_product_id>/commerce.inventory/daily`.
- `docs/plans/2026-05-25-tiendanube-exception-desk-technical-truth-gates.md` remains the right implementation plan for making the sales claim technically honest, but its current-facts/action-key notes should be refreshed to include the now-implemented `add_comment` operator action.

Implication: **sell an operator-assisted Exception Desk pilot, not finished self-serve SaaS**, until SKU-level stockout, stale suppression, owner-facing projection allowlists, and fulfillment truth gates are implemented and tested.

---

## External evidence checked

A subagent council researched buyer pain, Atlassian primitives, competitors, packaging, and GTM risks. Key public URLs were rechecked from the controller session and returned HTTP 200 at run time:

- Tiendanube NubeCommerce / ecommerce report: https://www.tiendanube.com/blog/ecommerce-informe/
- Tiendanube statistics help page: https://ayuda.tiendanube.com/es_CO/que-es-la-pagina-de-estadisticas
- Tiendanube WhatsApp Business guide: https://www.tiendanube.com/blog/whatsapp-business/
- Tiendanube app marketplace: https://www.tiendanube.com/tienda-aplicaciones-nube
- Tiendanube plans/pricing page: https://www.tiendanube.com/planes-y-precios
- Tiendanube Chat Nube solution page: https://www.tiendanube.com/soluciones/chat-nube
- Atlassian Jira issue/work-item docs: https://support.atlassian.com/jira-software-cloud/docs/what-is-an-issue/
- Atlassian Jira automation components: https://support.atlassian.com/cloud-automation/docs/components-in-jira-automation/
- Zapier pricing: https://zapier.com/pricing
- Gorgias pricing: https://www.gorgias.com/pricing

Market takeaways from the council:

1. Tiendanube has native statistics, stock tooling, apps, Chat Nube, and owned distribution; Orvo must avoid being a feature-level alert or dashboard.
2. WhatsApp is validated as a LatAm commerce surface, but Orvo must treat WhatsApp as a projection/delivery surface, not the source of truth.
3. Analytics apps, helpdesks, WhatsApp CRMs, ERPs, and automation tools already own adjacent jobs. Orvo’s wedge is **case lifecycle + evidence + follow-up memory**, not metrics display or message automation.
4. The Atlassian analogy should guide primitives: Jira issue/work item → Orvo `OperationalCase`; issue type → case family; workflow transition → audited action key; automation rule → deterministic detection/runtime policy; project/queue → operator case desk; app platform → connector registry.

---

## ICP and buyer pain

### Primary ICP

- Argentine/LatAm physical-goods D2C store.
- Tiendanube is the main storefront or at least a trusted operational source for orders/products/stock.
- Buyer/champion is owner-founder, ecommerce operator, or small team lead responsible for daily sales, stock, dispatch, customer escalation, and agency/team accountability.
- WhatsApp is already used for status requests, screenshots, decisions, customer follow-up, or daily operating rhythm.
- Store has enough order/SKU volume that a missed exception costs money, founder time, or customer trust.

### Strong early fit signals

- Owner asks “qué pasó hoy?” or asks staff/agency for daily screenshots/status.
- Many SKUs/variants and active promotions create stockout/oversell risk.
- Recent stockout, stale stock, underperforming sales day, or paid order stuck before dispatch.
- Tiendanube data is maintained well enough for deterministic detection.
- Someone is accountable for resolving cases.
- Buyer can name a recent operational miss that would have justified the pilot price.

### Poor fit signals

- Low-volume hobby store or service/digital-product business with little stock/fulfillment pain.
- Tiendanube stock/order data is known wrong and no one will fix source data.
- Buyer wants dashboards/exports, generic AI chat, guaranteed revenue lift, managed operations, or automatic edits to ads/stock/orders/refunds/messages.
- No accountable human owns follow-up; Orvo would become alert spam.

---

## Ranked sellable product opportunities

| Rank | Opportunity | Buyer promise | Build stance | Product area |
| ---: | --- | --- | --- | --- |
| 1 | **Tiendanube Exception Desk** | “Qué necesita atención hoy, por qué, con evidencia, y qué sigue abierto.” | Sell/pilot now as assisted/truth-gated. | Work Management Core + Operator Surfaces |
| 2 | **SKU-level stockout risk** | “No te quedes sin stock en productos que se están vendiendo o son importantes.” | Build next; flagship case. | Work Management Core |
| 3 | **Data stale / unsafe advice** | “Si Tiendanube o una fuente no está confiable, Orvo te lo dice y no inventa.” | Build next; trust moat and suppressor. | Connector Platform + Admin/Security |
| 4 | **Sales below configured floor** | “Ventas bajo el piso configurado; revisá tienda/pagos/tráfico.” | Secondary; only configured floor or safe baseline. | Workflow Automation |
| 5 | **Fulfillment backlog / pending paid orders** | “Revisá pedidos pagos pendientes antes de que reclame el cliente.” | Internal/backtest until field semantics pass truth gate. | Work Management Core + Connector Platform |
| 6 | **Meta Ads spend without orders** | “Se está gastando y no entran pedidos.” | Later Growth; strong ROI story after freshness parity. | Connector Platform + Workflow Automation |
| 7 | **Unanswered WhatsApp/support conversations** | “Chats de venta/soporte esperando demasiado.” | Later; useful but risks helpdesk/chatbot category drift. | Connector Platform + Operator Surfaces |
| 8 | **Marketplace/channel mix shift** | “Cambió dónde se están vendiendo los productos.” | Later Custom/Growth after Tiendanube wedge converts. | Connector Platform + Analytics-derived cases |

### Recommendation

The next paid SKU should **not** expand breadth. It should deepen ranks 1–3 until a buyer can trust the daily case desk.

---

## SKU hypothesis and commercial guardrails

### Pilot — Piloto Exception Desk Tiendanube + WhatsApp

- **Price:** USD 149 / 30 days or ARS equivalent at invoice time.
- **Includes:** 1 Tiendanube store, 1 WhatsApp destination/group, up to 2 recipients, daily scheduled exception brief, assisted setup, configured thresholds, internal/operator-assisted case queue/history, source freshness caveats, weekly review.
- **Owner-facing cases:** `data_stale`, verified/configured SKU-level `stockout_risk`, conservative `sales_drop` only when configured.
- **Internal/conditional:** `fulfillment_backlog` only after field audit; do not promise as live until verified.
- **Limits:** roughly <=500 monthly orders or <=300 active SKUs as first-fit boundary; no custom connectors, Meta Ads, WhatsApp inbox ingestion, guaranteed ROI, or autonomous actions.

### Starter — Orvo Exception Desk Starter

- **Price:** USD 79/mo design-partner; USD 99/mo public target after support/onboarding cost is known.
- **Includes:** one Tiendanube store, daily brief, 90-day case/run history, `data_stale`, SKU-level `stockout_risk`, configured sales floor if safe, basic lifecycle, `acknowledge_case`, `resolve_case`, `add_comment` if the API remains implemented and UI/projected affordance is tested.
- **Do not include:** Meta Ads, MercadoLibre, WhatsApp inbox, fulfillment promise by default, custom connectors, dashboards/BI exports, ERP/accounting/warehouse integration, unlimited recipients/checks/SKUs/history, autonomous external writes.

### Growth — Orvo Exception Desk Growth

- **Price:** USD 199/mo.
- **Use when:** buyer wants more operators/recipients, more checks, weekly review, comments/timeline depth, assignments, richer statuses, higher limits, recurring fulfillment workflow, or future Meta Ads `spend_without_orders`.
- **Gate:** do not sell workflow states/actions until code supports them.

### Custom — Orvo Operations Control Plane Custom

- **Price:** USD 399+/mo scoped.
- **Use when:** multi-store, agency portfolio, custom connectors, SLA/security/procurement, audit export, or managed service expectations.
- **Guardrail:** Custom must not pollute Starter; keep custom integrations behind explicit scope and margin protection.

---

## Product primitives to build next

### Work Management Core

1. `OperationalCase` remains the native object and source of truth.
2. SKU-level case identity for `stockout_risk`.
3. Evidence snapshots for every owner-facing number.
4. Deterministic dedupe/reopen/update behavior.
5. Timeline events for case opened/updated, evidence attached, operator comment, status change, and run/degraded reference.
6. Keep lifecycle narrow in Starter: `open -> acknowledged -> resolved`; only add `in_progress`/`dismissed` when implemented throughout models, store, API, tests, and projections.

### Workflow Automation

1. Deterministic detection policies; no LLM-created cases, priorities, metrics, lifecycle transitions, or action keys.
2. Stale-data suppression: unsafe connector states create/update `data_stale` and suppress/narrow downstream stock/sales/fulfillment advice.
3. Idempotency so daily runs update the same case instead of spamming a new alert.
4. Dry-run/backtest mode for case detection before owner-facing rollout.
5. Approval/audit gates before any external side effect.

### Connector Platform

1. Tiendanube connector capabilities must be registry-backed: products/SKUs, variants, inventory quantities, orders, timestamps/freshness, degraded states.
2. Secret refs only; no raw secrets in runtime artifacts, ledger metadata, logs, or examples.
3. Connector health and last-success state must feed run ledger and `data_stale` cases.
4. Fulfillment/pending-order field confidence must be explicitly normalized before owner-facing release.

### Operator Surfaces

1. WhatsApp brief is a projection of case state, not the system of record.
2. Internal operator queue filters: open, critical, data stale, stockout risk, case type, connector degraded, recently resolved.
3. Run history inspection: what ran, connector status, runtime/config hash, cases opened/updated, dispatch status, evidence refs, redaction status.
4. Action affordances should be code-whitelisted: currently safe to talk about `acknowledge_case`, `resolve_case`, and `add_comment`; do not show unsupported buttons.

### Admin/Security

1. Explicit tenant/business scope on every read/mutation.
2. Operator actor identity on comments/actions/status transitions.
3. Redaction at API/operator/brief boundaries.
4. Audit trail for case/action/config changes.
5. Track onboarding/support time per pilot as a product metric.

---

## Engineering-ready specs

### Spec A — SKU-level `stockout_risk`

**Product area:** Work Management Core + Operator Surfaces  
**Repo paths:** `app/brain/d2c_case_policies.py`, `app/brain/operational_cases.py`, `app/brain/operator_views.py`, `app/brain/reporting.py`, `tests/test_brain_d2c_case_policies.py`, `tests/test_operator_case_views.py`

**Detection:** open/update when SKU/product stock is at or below configured threshold and either recent units sold > 0 or SKU is explicitly marked important, with fresh Tiendanube inventory data.

**Suppress:** stale/missing inventory, missing SKU/product ID, non-moving SKU without strategic flag.

**Dedupe:** `<business_id>/stockout_risk/sku/<sku_or_product_id>/commerce.inventory/daily`.

**Evidence:** SKU/product ID, label, stock units, threshold, recent sales/window, important flag, freshness state, connector/run/artifact refs.

**Acceptance gates:**
- Two different SKUs create two cases.
- Repeated runs for same SKU update one case.
- Stale inventory opens/updates `data_stale` and does not open stockout.
- WhatsApp brief cites SKU-level evidence and does not hide source freshness caveats.

### Spec B — `data_stale` suppression policy

**Product area:** Connector Platform + Admin/Security + Work Management Core  
**Repo paths:** `app/brain/operational_cases.py`, `app/brain/runtime.py`, `app/brain/run_ledger.py`, `app/brain/execution_ledger.py`, `tests/test_brain_operational_cases.py`, `tests/test_run_orvo_brain_reports_script.py`

**Detection:** open/update when Tiendanube credentials fail, rate limits block safe execution, source freshness exceeds policy, malformed responses prevent safe metrics, or required fields are unavailable.

**Effect:** suppress or narrow downstream `stockout_risk`, `sales_drop`, and pending-order advice.

**Dedupe:** `<business_id>/data_stale/connector/<connector_type>/runtime.freshness/daily`.

**Evidence:** connector type, failure class, stale duration, latest run ID, last success if known, affected case families.

**Acceptance gates:**
- No owner-facing brief claims inventory/sales/order facts from stale Tiendanube data.
- Open `data_stale` cases appear in operator views and owner brief caveats.
- Recovery can be acknowledged/resolved only through audited operator action.

### Spec C — fulfillment backlog truth gate

**Product area:** Work Management Core + Connector Platform  
**Repo paths:** `app/brain/adapters/tiendanube.py`, `app/brain/operational_cases.py`, `app/brain/execution_ledger.py`, `docs/specs/d2c-case-family-catalog.md`, `tests/test_brain_tiendanube_adapter.py`, future `tests/test_brain_cases_fulfillment.py`

**Decision gate:** do not make owner-facing until real Tiendanube data proves Orvo can distinguish paid/unfulfilled/aging orders reliably and owner-facing projections have an explicit visibility/readiness allowlist.

**Normalize before release:** `is_paid`, `is_unfulfilled`, `is_cancelled_or_refunded`, `pending_since`, `age_hours`, `field_confidence`, redacted sample order refs, and source freshness.

**Suppress:** missing/ambiguous payment or fulfillment status, stale order source, external ERP/carrier truth source required but unavailable, pickup/preorder/split-shipment/test/cancelled/refunded ambiguity.

**Acceptance gates:**
- Backtest 2–3 real/sandbox stores.
- Compare Orvo pending-order count/oldest age against operator review.
- Before storing fulfillment backlog as an `OperationalCase`, add `fulfillment_backlog` to `OperationalCaseType` plus persistence/tests; until then, store only internal/backtest signals or artifacts outside the case system.
- Internal-only fulfillment cases are excluded from WhatsApp unless `owner_facing_ready == true`, `field_confidence == "verified"`, freshness is safe, and redacted evidence snapshots exist.

### Spec D — pilot COGS and usefulness instrumentation

**Product area:** Admin/Security + GTM operations  
**Repo paths:** `docs/ops/d2c-pilot-readiness-checklist.md`, `docs/ops/d2c-pilot-runbook.md`, future lightweight pilot tracking file or operator admin model.

**Track per pilot:** setup minutes, connector/debug minutes, threshold configuration minutes, manual review minutes, weekly review minutes, useful cases/week, false-positive rate, brief reads/replies/actions, manual checks replaced, cases resolved, and owner objections.

**Acceptance gates:**
- Path to <60-minute repeatable onboarding for Starter.
- Weekly support/review <=30–45 minutes unless priced as Growth/Custom.
- At least 3 buyer-validated useful cases in 30 days for qualified stores.
- Owner/operator engages with brief at least 3 times/week or explicitly says it replaced a manual check.

---

## What not to build now

- Generic chatbot or “ask your store anything.”
- Dashboard-first UI detached from cases/actions.
- ERP/accounting/WMS/payment reconciliation.
- WhatsApp inbox/helpdesk replacement.
- Attribution/MMM/ROAS suite.
- Zapier/Make clone or broad no-code automation builder.
- Public marketplace/developer SDK.
- Autonomous external actions to ads, stock, prices, refunds, orders, or customer messages.
- Broad Growth tier claims before the Tiendanube exception desk converts.
- Fulfillment owner-facing claims until field confidence and projection allowlist exist.

---

## Strongest next GTM experiments

1. **Paid design-partner close test** — 30–50 target stores, 10–20 calls, ask for 3–5 USD 149 pilots upfront. Pass if qualified buyers pay for the narrow Exception Desk, not custom dashboards/connectors.
2. **Wizard-of-Oz daily exception desk** — for 3–5 stores, manually review Tiendanube cases before WhatsApp delivery while tracking false positives, actions taken, and time spent.
3. **30-day data backtest** — backtest stockout, data-stale, sales-floor, and internal fulfillment signals on 2–3 stores; measure actionable cases/week and noisy cases.
4. **Onboarding stopwatch** — record all setup, connector, data-audit, threshold, WhatsApp, review, support, and debug minutes.
5. **Positioning test** — compare “daily WhatsApp report” vs “ecommerce dashboard” vs “Tiendanube exception desk with evidence/follow-up”; win only if buyers choose exception desk and name a replaced manual process.
6. **Pause test** — after 10–14 days, pause the brief or ask if they would miss it; pass if buyer notices, resumes manual checks, or asks to continue paid.

---

## Kill criteria

Pause, kill, or reposition if any of these persist:

- Fewer than 3 of 10 qualified stores agree to pay upfront for the USD 149 pilot.
- Buyers only pay if it includes custom connectors, dashboards, agency review, or autonomous actions.
- Fewer than 3 buyer-validated useful cases appear in a 30-day pilot for otherwise qualified stores.
- Owner/operator reads/replies fewer than 3 times/week and no manual check is replaced.
- False positives exceed trust tolerance: more than ~10–20% of owner-facing cases judged not useful, or any severe case materially wrong.
- Any unsupported owner-facing claim appears: stale data treated as fresh, wrong stock/order status, unverified fulfillment claim.
- Onboarding takes >2–3 hours per store with no path to reduce.
- Weekly human review/support exceeds 30–45 minutes at Starter-equivalent price.
- More than 40% of qualified stores lack reliable Tiendanube stock/order data and are unwilling to fix source hygiene.

---

## Next 7-day priority

**Priority rule:** milestone lane wins coding, testing, integration, and review capacity. Product/market work should sharpen the paid pilot and customer discovery; engineering should finish only the truth gates needed to avoid false claims.

1. Execute the existing technical plan: `docs/plans/2026-05-25-tiendanube-exception-desk-technical-truth-gates.md`, with a facts refresh for the implemented `add_comment` action.
2. Narrow all external sales language to: **Mesa diaria de casos operativos para Tiendanube con evidencia y seguimiento por WhatsApp**.
3. Recruit 10–20 qualified Tiendanube physical-goods operators and ask for USD 149 paid pilot commitments.
4. Backtest real/sandbox Tiendanube data for SKU-level stockout and stale suppression before promising owner-facing cases.
5. Add the owner-facing WhatsApp/brief projection allowlist/readiness gate before any non-assisted rollout.
6. Keep Meta Ads, WhatsApp inbox ingestion, MercadoLibre, dashboards, custom connectors, and autonomous actions out of the first paid SKU.

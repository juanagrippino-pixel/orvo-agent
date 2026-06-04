# Orvo Tiendanube Exception Desk Opportunity Spec

Status: Product & Market Intelligence recommendation
Date: 2026-05-24
Related:
- `docs/product/d2c-control-plane-prd.md`
- `docs/gtm/d2c-packaging-and-messaging.md`
- `docs/gtm/d2c-pricing-packaging-hypothesis.md`
- `docs/research/2026-05-24-tiendanube-latam-d2c-buyer-pain-icp.md`
- `docs/research/2026-05-24-orvo-competitor-landscape.md`
- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/d2c-operator-surface-contract.md`
- `docs/roadmap/d2c-control-plane-roadmap.md`

## Executive recommendation

Keep the internal product direction: Orvo is a D2C ecommerce operations control plane with connector registry, compiled runtime, run ledger, deterministic metrics, Operational Cases, workflow state, evidence, and operator projections.

Sharpen the buyer-facing first product from broad "D2C control plane" into:

> **Orvo Tiendanube Exception Desk** — daily Tiendanube exception monitoring over WhatsApp: SKU-level stockout risk, stale/data-unsafe states, and conservative sales-floor exceptions, each with evidence and open/resolved memory. Aging paid/unfulfilled orders stay truth-gated until Tiendanube payment/fulfillment fields are verified for the store.

Reason: SMB buyers do not buy "control planes" or "cases" as abstractions. They buy concrete operational risk detection: specific products about to run out, data/source failures that make advice unsafe, and only later paid orders stuck before fulfillment once the evidence path is reliable.

## ICP and buyer pain

### Primary ICP

- Argentine/LatAm physical-goods D2C store.
- Tiendanube is the main storefront or an important source of commerce truth.
- Owner/founder, ecommerce operator, or small team manages stock, orders, fulfillment, WhatsApp, ads, agencies, and spreadsheets manually.
- Enough SKU/order volume that missed exceptions cost sales, customer trust, founder time, or agency/team accountability.
- WhatsApp is already a daily operating surface.

### Strong fit signals

- Repeated stockouts, overselling, or promotion of low-stock products.
- Paid orders aging before dispatch or customers asking where orders are.
- Owner asks staff/agency for daily screenshots/status.
- Tiendanube stock/order status is maintained well enough to detect exceptions.
- The business has someone accountable for handling each exception.

### Poor fit signals

- Very low-volume hobby store.
- Pure digital products with no stock/fulfillment pain.
- Inventory and fulfillment are not updated in Tiendanube and no reliable substitute source is available.
- Buyer wants only dashboards, generic AI chat, or guaranteed revenue lift.
- Buyer expects Orvo to automatically change ads, stock, prices, refunds, or customer messages immediately.

## Ranked sellable opportunities

### 1. Tiendanube Stock + Data-Freshness Exception Desk

**Rank:** 1

**Buyer promise:** Orvo watches Tiendanube and tells the operator what needs action today: moving or important SKUs at risk of stockout, data problems that make advice unsafe, and conservative sales-floor misses when configured.

**Why this wins first:**

- Concrete and operational, not abstract analytics.
- Mostly Tiendanube-first; does not require Meta Ads, MercadoLibre, WhatsApp ingestion, or attribution.
- Deterministic and evidence-friendly.
- Naturally creates durable workflow state: open, acknowledged, in progress, resolved, dismissed.
- Differentiates against dashboards, chatbots, ERPs, and point apps.

**Required case families:**

1. `stockout_risk` at SKU/product scope.
2. `data_stale` with suppression of unsafe downstream advice.
3. Optional conservative `sales_drop` only with owner-configured floor or very trustworthy baseline.
4. `fulfillment_backlog` as an internal/backtest truth-gated candidate until real Tiendanube fields prove reliable.

**Primary product area:** Work Management Core + Operator Surfaces.

**Engineering paths:**

- `app/brain/adapters/tiendanube.py`
- `app/brain/pipeline.py`
- `app/brain/runtime.py`
- `app/brain/run_ledger.py`
- `app/brain/connector_registry.py`
- future/additive `app/brain/cases/*`
- `app/brain/reporting.py`
- `server.py`
- tests under `tests/test_brain_tiendanube_*`, `tests/test_brain_run_ledger.py`, future `tests/test_brain_cases*.py`

### 2. Meta Ads Spend Without Orders

**Rank:** 2

**Buyer promise:** Orvo warns when ads are spending but Tiendanube orders are not following.

**Why it is attractive:** Clear ROI narrative and likely Growth-tier expansion.

**Why not first:** Needs Meta Ads + Tiendanube freshness parity, careful thresholds, and false-positive control. It risks pulling Orvo into attribution/ROAS fights before the Tiendanube-only exception desk proves value.

**Case family:** `spend_without_orders`

**Primary product area:** Workflow Automation + Connector Platform.

**Engineering paths:**

- `app/brain/adapters/meta_ads.py`
- `app/brain/adapters/tiendanube.py`
- `app/brain/connector_registry.py`
- `app/brain/run_ledger.py`
- future/additive `app/brain/cases/*`
- tests under `tests/test_brain_meta_ads_*`, `tests/test_brain_tiendanube_*`, future cross-source case tests

### 3. WhatsApp/Support Unanswered Conversations

**Rank:** 3

**Buyer promise:** Orvo shows sales/support conversations waiting too long.

**Why it is attractive:** Very concrete and WhatsApp-native.

**Why not first:** Data access is fragmented across personal WhatsApp, WhatsApp Business App, WhatsApp Business Platform providers, CRMs, and helpdesks. Privacy and API/provider complexity can swamp the first Tiendanube-only proof.

**Case family:** `unanswered_conversations`

**Primary product area:** Connector Platform + Operator Surfaces.

**Engineering paths:**

- future `app/brain/adapters/whatsapp_*` or helpdesk connector
- `app/brain/connector_registry.py`
- future/additive `app/brain/cases/*`
- `app/brain/reporting.py`
- `server.py`

### 4. Daily Sales Drop Brief

**Rank:** 4

**Buyer promise:** Orvo tells the owner when sales/orders are below expected.

**Why lower:** Often obvious, noisy without baseline, and weakly actionable without root-cause evidence. Keep as a conservative case, not flagship positioning.

**Case family:** `sales_drop`

**Rule:** only open when an explicit owner-configured floor exists or the baseline is trustworthy and tested. Phrase as "sales below configured floor," not AI anomaly/root-cause certainty.

## First sellable package/SKU hypothesis

### Pilot: Piloto Tiendanube + WhatsApp

- **Price hypothesis:** USD 149 / 30 days, ARS equivalent at invoice time.
- **Goal:** validate daily usefulness, onboarding burden, evidence quality, and willingness to pay.
- **Included:** 1 Tiendanube store, 1 WhatsApp destination/group, daily exception brief, assisted setup, evidence-backed case queue/history, run health/degraded caveats, one weekly review or async improvement note.
- **Case families:** launch with SKU-level `stockout_risk` and `data_stale`; include `sales_drop` only if configured floor/baseline is safe. Keep `fulfillment_backlog` internal/backtest-only until the fulfillment truth gate passes.
- **Limits:** 30 days, up to ~500 monthly orders or ~300 active SKUs as fit signal, no custom connectors, no guaranteed revenue lift, no autonomous external actions.

### Starter: Orvo Operaciones Starter

- **Price hypothesis:** USD 79/mo or ARS equivalent; setup may be charged after design-partner phase.
- **Included:** Tiendanube connector/runtime, daily WhatsApp exception brief, deterministic case queue/history, evidence snapshots, run ledger inspection for Orvo/operator support, configured thresholds, data freshness/degraded alerts, basic open/update/resolve/dismiss lifecycle.
- **Do not include:** Meta Ads, MercadoLibre, custom connectors, generic dashboard exports, ERP/accounting/warehouse integration, autonomous external actions, unlimited history/SKUs/checks.

### Growth: Orvo Operaciones Growth

- **Price hypothesis:** USD 199/mo or ARS equivalent.
- **Included:** Starter plus comments, assignment, acknowledge/in-progress/resolve/dismiss workflow depth, visible timeline, weekly case review, stronger freshness monitoring, Growth expansion cases such as `spend_without_orders` when implemented and verified, more recipients, and one additional standard connector when supported.
- **Do not include:** unlimited stores/connectors, bespoke ERP work, full BI replacement, 24/7 SLA, full helpdesk/chatbot suite, developer marketplace, or guaranteed revenue lift.

## Product primitives to build next

### Work Management Core

1. `OperationalCase` model/storage/engine for SKU-level `stockout_risk` and `data_stale`; `fulfillment_backlog` remains a gated expansion spec until implemented and validated.
2. Stable dedupe keys per case family and entity scope.
3. Evidence snapshots for every owner-facing number.
4. Lifecycle: `open -> acknowledged -> in_progress -> resolved`, plus `dismissed` and `reopened`.
5. Timeline events for case opened, evidence attached, status transition, operator comment, action requested/completed/failed, run/degraded reference.

### Workflow Automation

1. Deterministic open/update/reopen/suppress policies.
2. Dry-run/simulation for case detection.
3. Idempotency so repeated runs update cases rather than spam alerts.
4. Registered action keys only; no LLM-created actions.
5. Approval/audit gates before any external side effect.

### Connector Platform

1. Tiendanube capabilities registered before runtime use:
   - products/SKUs
   - inventory quantities where available
   - orders
   - payment/fulfillment status
   - timestamps/freshness
   - typed degraded states
2. Secret refs and redaction invariants.
3. Connector health and last-success state surfaced into run ledger and `data_stale` cases.
4. Certification tests for Tiendanube case inputs.

### Operator Surfaces

1. WhatsApp exception brief as a projection of cases, not the source of truth.
2. Internal case queue with filters: open, high priority, connector degraded, case type, entity scope.
3. Case timeline for evidence and follow-up.
4. Run history/inspection: what ran, connector status, runtime/config hash, cases opened/updated, dispatch status, redaction check.
5. Manual actions: acknowledge, assign owner, add comment, mark in progress, resolve, dismiss.

### Admin/Security

1. Explicit tenant/business scope on all reads/mutations.
2. Operator identity on status/comments/actions.
3. Audit events for case/action/config changes.
4. Redaction tests for tokens, API keys, OAuth values, URLs, service-account content, and connector artifacts.
5. Retention/export policy before broader live use.

## Engineering-ready proof slice

### Spec A: `stockout_risk`

**Detection:** Open/update when a product/SKU has stock at or below configured threshold, recent sales velocity is positive or the SKU is marked important, and Tiendanube inventory data is fresh.

**Suppress:** Do not alert if inventory data is stale; create/update `data_stale` instead. Do not alert on non-moving SKUs unless explicitly marked important.

**Evidence:** product/SKU, label, current stock, recent units sold/window, threshold, source freshness, latest run ID.

**Actions:** `confirm_stock`, `pause_promotion` as recommendation only, `add_comment`, `resolve_case`, `dismiss_case`.

**Repo paths:**

- Add/modify case contracts under future `app/brain/cases/models.py` and `app/brain/cases/engine.py`.
- Source metrics from `app/brain/adapters/tiendanube.py` and `app/brain/pipeline.py`.
- Persist in future `app/brain/cases/storage.py` plus existing `app/brain/storage.py` patterns.
- Render projection in `app/brain/reporting.py`.
- Test in future `tests/test_brain_cases_stockout.py` and existing Tiendanube adapter/pipeline tests.

### Spec B: `fulfillment_backlog` truth gate

**Detection:** Do not open owner-facing cases yet. First backtest/audit whether paid/unfulfilled order count and oldest paid/unfulfilled order age can be derived reliably for the store.

**Suppress:** Do not alert if order/fulfillment fields are missing, ambiguous, or stale; create/update `data_stale` with affected advice instead.

**Evidence:** affected order count, oldest order age, redacted safe order refs, payment/fulfillment status grouping, source freshness, latest run ID.

**Actions:** Treat `inspect_pending_orders`, `assign_owner`, `add_comment`, `mark_in_progress`, `resolve_case`, and `dismiss_case` as roadmap/catalog keys unless implemented in code. Current implemented actions are `acknowledge_case` and `resolve_case` only.

**Repo paths:**

- Extend `docs/specs/d2c-case-family-catalog.md` if this becomes first-wave accepted scope.
- Implement under future `app/brain/cases/*`.
- Verify Tiendanube order/fulfillment fields in `app/brain/adapters/tiendanube.py`.
- Add pipeline/evidence tests in `tests/test_brain_tiendanube_pipeline.py` and future `tests/test_brain_cases_fulfillment.py`.

### Spec C: `data_stale`

**Detection:** Open/update when Tiendanube credentials fail, API is unauthorized, API is rate-limited, source data is older than policy, or malformed responses prevent safe advice.

**Effect:** Narrow or suppress downstream advice; owner-facing output must say what was not used and why.

**Evidence:** connector type, connector ID, failure class, stale duration, last successful run timestamp, affected case families/advice, latest run ID.

**Actions:** `refresh_credentials`, `retry_connector`, `add_comment`, `resolve_case` after successful freshness recovery.

**Repo paths:**

- Use `app/brain/connector_registry.py`, `app/brain/run_ledger.py`, and `app/brain/runtime.py` for connector results and stale states.
- Add case creation under future `app/brain/cases/engine.py`.
- Surface in `app/brain/reporting.py` and `server.py` inspection endpoints.
- Test in `tests/test_brain_run_ledger.py`, `tests/test_brain_connector_registry.py`, future `tests/test_brain_cases_data_stale.py`.

### Spec D: Conservative `sales_drop`

**Detection:** Open/update only when current orders/revenue falls below an explicit configured minimum or a trustworthy baseline with sufficient data and freshness.

**Suppress:** Missing baseline, stale commerce source, or insufficient comparison data must suppress or downgrade to informational; do not invent root cause.

**Evidence:** current orders/revenue, configured floor or comparison window, freshness, latest run ID.

**Actions:** `check_storefront`, `review_ads_changes`, `inspect_payment_or_checkout`, `add_comment`, `resolve_case`, `dismiss_case`.

**Repo paths:**

- Existing `app/brain/insights.py` and `app/brain/config.py` thresholds may feed this during migration.
- Future case state under `app/brain/cases/*`.
- Compatibility tests in `tests/test_brain_insights.py`, `tests/test_brain_pipeline.py`, future case tests.

## Competitor/Atlassian analogy evidence

### Competitor pattern

- Tiendanube ecosystem apps solve point jobs: ERP-lite, shipping, invoicing, WhatsApp/chat, marketplace sync, alerts. Orvo should not replace them; it should coordinate exceptions across them.
- Ecommerce BI/analytics tools show metrics and attribution. Orvo should avoid a dashboard category war and turn metrics into cases with workflow state.
- Helpdesks and WhatsApp CRMs own customer conversations. Orvo should treat unanswered conversations as a signal later, not become the inbox.
- ERPs own records, invoices, stock movements, and fiscal workflows. Orvo should stay the exception/workflow control plane above records, not become the source of financial truth.
- iPaaS/automation tools execute rules. Orvo should decide deterministically what becomes an operational case, then govern actions with audit and approvals.

### Atlassian primitive analogy

Copy the durable mechanics, not the breadth:

- Jira issue/work item -> `OperationalCase`.
- Issue types/custom fields -> D2C case families and evidence schemas.
- Workflows -> deterministic case lifecycle and transition audit.
- Queues/saved filters -> ecommerce operator queue.
- Jira activity/timeline -> case timeline and evidence history.
- Jira Automation -> narrow trigger/condition/action rules with dry-run and audit.
- Marketplace/Forge/Connect -> connector registry, scopes, manifests, certification tests; defer public marketplace.
- Admin/Guard -> tenant scope, RBAC, redaction, audit, secret indirection.
- JSM SLAs -> connector freshness and unresolved critical case timers.

## What not to build now

- Generic chatbot or "ask your store anything."
- Standalone dashboards detached from cases/actions.
- Full ERP/accounting/inventory/warehouse/payment reconciliation.
- Full customer helpdesk or WhatsApp inbox.
- Attribution/MMM/ROAS suite as the first category.
- Broad iPaaS/Zapier-style automation.
- Marketplace/developer SDK before the Tiendanube wedge is reliable.
- Autonomous external changes to ads, stock, orders, refunds, or messages without explicit case/action governance and approval.
- Polished UI before paid pilot proof that daily exception monitoring is valuable.

## Discovery questions for pilots

1. Is Tiendanube the source of truth for products/SKUs, stock, orders, and fulfillment status?
2. How many orders and active SKUs do you have per month?
3. Who checks Tiendanube every day, and what happens when they forget?
4. In the last month, did you run out of stock or oversell an item that was still being promoted?
5. How often do paid orders get stuck before dispatch?
6. What is the oldest paid/unfulfilled order age that becomes unacceptable?
7. Who should receive WhatsApp exceptions, and who resolves them?
8. What counts as resolved for a stock case or stuck-order case?
9. Would you pay for a 30-day pilot if it catches stock/order exceptions and keeps follow-up history?
10. What would make you cancel after two weeks?

## Decision needed

Product should not promote `fulfillment_backlog` into the first sellable proof slice until Tiendanube order/payment/fulfillment field semantics are audited against real stores and backtests. The first paid proof slice is SKU-level `stockout_risk` + `data_stale` + optional configured `sales_drop`.

Recommended decision: keep `fulfillment_backlog` internal/backtest-only for now; position `sales_drop` as "sales below configured floor," not broad anomaly detection.

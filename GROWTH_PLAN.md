# Orvo Brain — Growth Plan

Status: planning document only. No feature implementation is authorized by this document.

Scope: growth after structural hardening is complete: `conversation/` and `brain/` are separated, god-files are decomposed, connector worker pattern is documented, observability has correlation IDs, and current tests/contracts remain green.

Non-negotiable rules:

- Preserve `docs/specs/` contracts.
- Preserve the connector worker pattern in `docs/operability/connector-worker-runbook.md`: validate -> fetch -> build_report -> emit_metrics -> record_freshness.
- Keep owner/operator surfaces as projections of runtime/case state; do not make WhatsApp or conversational text the source of truth.
- LLM/copy layers may explain/rephrase, but must not invent metrics, cases, priorities, action keys, or lifecycle transitions.
- Every growth axis must be a bounded goal/capability, not a mega-project.
- Workflow automation with external or case-mutating side effects remains blocked until durable action ledger/approval gates are implemented.

---

## 1. Superficie actual

### 1.1 Connector surface already present

Current registry/runtime surface includes these connector types:

| Connector | Status in codebase | Current metric families | Growth role |
| --- | --- | --- | --- |
| `csv` | Registered adapter/runtime path. | `commerce.orders`, `commerce.revenue`, `commerce.inventory`, `runtime.freshness`, `runtime.data_quality` | Cheapest backfill/manual source; useful for onboarding and replay. |
| `google_sheets` | Registered adapter/runtime path. | `commerce.orders`, `commerce.revenue`, `commerce.inventory`, `runtime.freshness`, `runtime.data_quality` | Cheap manual/import source when native connectors are unavailable. |
| `tiendanube` | Registered adapter/runtime path and first wedge source. | `commerce.orders`, `commerce.revenue`, `commerce.inventory`, `runtime.freshness`, `runtime.data_quality` | Primary D2C/LatAm commerce source. |
| `mercadolibre` | Registered adapter/runtime path. | `commerce.orders`, `commerce.revenue`, `commerce.average_order_value`, `runtime.freshness`, `runtime.data_quality` | Marketplace channel expansion. |
| `meta_ads` | Registered adapter/runtime path. | `ads.spend`, `ads.delivery`, `ads.roas`, `runtime.freshness`, `runtime.data_quality` | Paid-media depth and cross-source `spend_without_orders`. |
| `sample` | Registered manual payload path. | `manual.payload`, `runtime.freshness`, `runtime.data_quality` | Tests/demos/projections only. |

Important caveat: current registry specs include `required_secret_refs`, but adapters still have transitional inline secret params for Tiendanube/MercadoLibre/Meta Ads. Packet Q must close that before calling the connector platform fully compiled-runtime-ready.

### 1.2 Cost ranking for new connectors

Cost is relative to the already documented worker pattern and existing canonical models. `cheap` means one bounded adapter/spec/test goal can plausibly add preview/forced/scheduled read-only DailyReport support without changing core contracts. `expensive` means OAuth/provisioning, metric taxonomy, freshness, case-family promotion, or side-effect governance becomes material.

| Candidate | Relative cost | Why | Best first bounded goal |
| --- | ---: | --- | --- |
| WooCommerce | Low/medium | Commerce shape is close to Tiendanube: orders, revenue, products/inventory. API is straightforward, but store URLs, auth modes, and plugin/version drift need validation. | Add read-only `woocommerce` connector emitting commerce orders/revenue/freshness, with inventory optional. |
| Shopify | Medium | Commerce model maps well to current families and has strong APIs, but real production use needs OAuth app flow, scopes, webhooks/rate limits, and multi-tenant credential handling. | Add registry spec + read-only DailyReport adapter for orders/revenue; defer OAuth self-service to a separate goal. |
| PrestaShop | Medium/high | Same commerce concepts, but version/module/self-hosting variability makes auth, endpoints, currency/tax, and product/inventory semantics less predictable. | Add compatibility audit + one read-only adapter for a pinned PrestaShop API/version; do not generalize immediately. |
| TikTok Ads | Medium/high | Similar conceptual lane to Meta Ads but different attribution windows, campaign/account hierarchy, OAuth/scopes, rate limits, and ads metric semantics. Cross-source cases depend on commerce freshness. | Add read-only spend/delivery adapter; keep owner-facing recommendations gated behind stale-source suppression. |
| Google Ads | High | Valuable, but ads semantics, OAuth, MCC/account hierarchy, quota/developer-token approval, conversion mapping, and ROAS evidence are heavier than Meta/TikTok. | Add connector spec/readiness contract first; implement adapter only after ads metric contract hardens. |
| WhatsApp/support inbox connector | High | Unlocks `unanswered_conversations`, but conversation ownership, privacy, webhook idempotency, message refs, and support-state semantics need careful source-of-truth boundaries. | Add event/freshness contract and read-only unanswered-count projection; no automated replies. |
| ERP/fulfillment/shipping connectors | High | Enables `fulfillment_backlog`, but each provider has heterogeneous order states, carrier events, and customer-impact risk. | Add one provider-specific read-only backlog adapter after fulfillment case contract is narrowed. |

Cheapest near-term connector expansion is not automatically the highest-value one. CSV/Sheets/WooCommerce-style commerce connectors widen onboarding, while Shopify may be strategically bigger but should be split into read-only adapter first and OAuth/self-service later.

### 1.3 Control-plane parts ready to scale

Ready or close to ready for more clients:

- **Domain separation:** conversational layer is no longer tangled with Brain/core runtime.
- **Connector worker boundary:** adapter factories are allowlisted through registry metadata, and worker stages are explicit.
- **Runtime compiler shape:** compiled runtime strips raw secrets into secret refs and validates connector specs.
- **Metric/case discipline:** metric registry and case family docs constrain owner-facing claims.
- **Operational Cases:** cases have lifecycle/status/action concepts and operator projections.
- **Read-only/internal operator surfaces:** `/internal/brain/*` surface is modular and contract-tested.
- **Run/config/case SQLite stores:** enough for concierge/private pilots and repeatable local/runtime operation.
- **Observability baseline:** structured logs and correlation/request IDs exist for core runtime paths.
- **Redaction discipline:** docs/specs/tests require redaction; runtime paths have redaction helpers and canary tests.

Not ready for broad scale/live self-service:

- **Packet O — durable operator audit is still a blocker:** role helpers exist, but durable `operator_audit`/least-privilege closure is not complete.
- **Packet Q — secret-ref execution is still transitional:** current compiled runtime has secret refs, but connector execution still relies on legacy inline token params in key adapters.
- **Packet U — durable workflow action ledger/approval objects do not exist yet:** workflow automation is projection/dry-run only.
- **Multi-tenant admin model is minimal:** `business_id` scoping exists, but no full workspace/project/org model, tenant onboarding lifecycle, audit export, billing, or support/admin console.
- **Storage migration posture is early:** SQLite is acceptable for Phase A/concierge, but durable migrations, backup/restore, retention, and audit tables are not complete enough for larger live use.
- **APM/SLO surface is baseline-only:** logs have correlation IDs, but no first-class metrics dashboards, tracing, alerting, run health SLOs, or tenant-level incident views.
- **OAuth/self-service provisioning is not productized:** connectors can be configured, but no safe user-facing OAuth/install flow with secret refs, validation, and reconnect UX.

---

## 2. Ejes de crecimiento posibles

This section lists candidate axes without choosing one as mandatory. Each axis must remain a separate bounded goal.

### Axis A — More connectors

**Benefit:** widens addressable market and makes Orvo less Tiendanube-only.

**Cost:** medium. Adapter implementation is now more disciplined, but each connector still needs registry spec, secret refs, emitted metric families, stale/failure handling, tests, docs, and runtime integration.

**Good bounded goals:**

1. `woocommerce` read-only commerce DailyReport adapter.
2. `shopify` read-only commerce DailyReport adapter.
3. `tiktok_ads` read-only ads spend/delivery adapter.
4. `prestashop` pinned-version compatibility adapter.

**Risks:** connector sprawl, semantic metric drift, stale-source false advice, OAuth/secret shortcuts.

**Must respect:** connector registry contract, compiled runtime contract, metric registry envelope, worker runbook.

### Axis B — More depth in Operational Cases / new case families

**Benefit:** increases product value for existing clients without requiring many new integrations. Moves Orvo from reporting to actual operating system.

**Cost:** low/medium for existing data families; high for families needing new data sources.

**Current family readiness:**

- `sales_drop`: viable with Tiendanube/CSV/Sheets/MercadoLibre commerce metrics.
- `stockout_risk`: viable when inventory/product data is fresh.
- `data_stale`: essential and should deepen with every connector.
- `spend_without_orders`: depends on fresh ads + commerce sources.
- `fulfillment_backlog`: depends on reliable fulfillment/order-status data.
- `unanswered_conversations`: depends on WhatsApp/support source freshness.
- `channel_mix_shift`: explicitly deferred/internal until multi-channel metrics and registry promotion are green.

**Good bounded goals:**

1. Deepen `data_stale` with connector-specific remediation and affected-case-family projection.
2. Promote one new or underused family only when evidence contracts are green, e.g. `fulfillment_backlog` for Tiendanube order status.
3. Add source-specific dedupe/reopen tests for one case family.

**Risks:** owner-facing false positives, unsupported recommendations, duplicate daily cases, hidden stale data.

**Must respect:** `docs/specs/d2c-case-family-catalog.md`, `docs/specs/d2c-action-key-catalog.md`, semantic metric registry.

### Axis C — More capability in conversational agents

**Benefit:** improves customer/operator experience and can make Orvo feel more useful through follow-up questions, explanations, and guided resolution.

**Cost:** medium. The hardening made `conversation/` separate, but the rule remains: conversations are projections and routing surfaces, not the source of truth.

**Good bounded goals:**

1. Case-aware explanation replies: answer "por qué me avisaste esto" using only case evidence snapshots.
2. Owner follow-up intake: attach an owner reply as a case comment/request, not as a hidden state mutation.
3. Operator handoff escalation copy: deterministic templates from case status/action key.

**Risks:** LLM invents metrics/actions, conversation bypasses case action governance, privacy leaks.

**Must respect:** action key catalog, operator surface contract, audit/timeline requirements.

### Axis D — Workflow automation with real mutations

**Benefit:** major control-plane leap: Orvo can move from recommendations to governed actions.

**Cost:** high. This axis is explicitly blocked until Packet U is complete, and Packet U itself depends on Packet O.

**Current state:** `workflow_automation.py` produces dry-run/planned action projections with idempotency keys and redacted audit-shaped payloads. It does not persist durable approval objects or execute side effects.

**Good bounded goals:**

1. Packet U foundation only: durable workflow action ledger and approval object, no external side effects.
2. Manual/operator case mutation idempotency enforcement.
3. One approval-required action lifecycle in storage, still no external API call.
4. Later: one safe internal mutation behind approval, then one external side effect only after audit/approval/idempotency gates are proven.

**Risks:** invisible state mutation, duplicate external actions, unauthorized action, weak rollback, compliance/audit gaps.

**Must respect:** Packet O first, Packet U, operator API contract, action key catalog.

### Axis E — Multi-client real / self-service onboarding

**Benefit:** converts concierge system into scalable SaaS/control plane.

**Cost:** high. Requires tenant/workspace/project/admin model, onboarding status, secret refs, OAuth/reconnect, RBAC/audit, config validation UX, and supportability.

**Good bounded goals:**

1. Read-only tenant/business inventory endpoint and admin projection.
2. Connector readiness/preflight preview for one business config without executing side effects.
3. Secret-ref onboarding record model, after Packet Q.
4. One self-service connector install flow, after Packet O/Q and storage migration gates.

**Risks:** cross-tenant data leak, secret leak, unsupported connector state, missing audit, accidental live mutation.

**Must respect:** Packet O, Packet Q, storage migration contract, tenant-secret redaction contract.

### Axis F — Observability/APM for scale

**Benefit:** makes multi-client operations supportable: failed runs, stale data, degraded connectors, dispatch failures, and operator incidents become visible before customers complain.

**Cost:** medium. Baseline structured logs exist, but product-grade APM needs metrics, dashboards, alerts, run health summaries, and incident/tenant views.

**Good bounded goals:**

1. Runtime health summary endpoint from run ledger + connector freshness.
2. Structured metric counters for run status, connector failure class, dispatch status, and case mutations.
3. Alerting thresholds/runbook for stale critical connectors.
4. Tenant-level SLO report for scheduled report freshness and delivery.

**Risks:** observability becomes another inconsistent source of truth, noisy alerts, logging sensitive data.

**Must respect:** run ledger foundation, redaction contract, correlation IDs, no raw secrets/log payloads.

---

## 3. Dependencias y orden

### 3.1 Dependency map

| Growth axis | Depends on | Hard blocker before live use | Notes |
| --- | --- | --- | --- |
| More connectors | Connector registry, worker runbook, metric registry. | Packet Q for secret-ref execution if connector needs real credentials. | Read-only preview adapters can land before full self-service if secrets are isolated and tests prove redaction. |
| Deeper case families | Metric registry, case family catalog, source freshness, evidence snapshots. | Semantic family alignment and stale-source suppression. | Do not promote `channel_mix_shift` owner-facing until registry/semantic promotion is explicit. |
| Conversational agents | Conversation/Brain boundary, operator surface contract, action catalog. | Packet O for mutations; Packet U for workflow/action requests. | Explanations can be read-only earlier; comments/mutations require audit. |
| Workflow automation with mutations | Current dry-run workflow projection, action catalog. | Packet O then Packet U. | No external actions before durable ledger, approvals, idempotency, and audit. |
| Multi-client/self-service | Business/config stores, runtime compiler, connector registry. | Packet O + Packet Q + storage/admin model. | Concierge multi-client can exist earlier; self-service/live onboarding should wait. |
| Observability/APM | Run ledger, structured logging, connector health taxonomy. | Redaction/tenant-scope checks for dashboards and alerts. | Safe to start before features, as long as it reads canonical ledger/case state. |

### 3.2 Follow-ups that should close before each axis

#### Packet O — Trust/Admin/Security audit closure

Close before:

- mutating operator surfaces beyond local/dev;
- conversational owner replies that create comments or change case state;
- workflow automation with durable actions;
- multi-client self-service/admin surfaces;
- any broad expansion of internal operator controls.

Acceptance reminders:

- denied/failed case actions audited where actor/business/case context exists;
- auth failures handled via safe pre-auth audit shape or explicitly documented as impossible without trusted context;
- audit payloads redacted before persistence;
- every internal route enforces relevant role permission with viewer/operator/admin tests;
- least-privilege/action-scope behavior is explicit.

#### Packet Q — Connector registry secret-ref runtime hardening

Close before:

- calling connector platform compiled-runtime complete;
- self-service connector onboarding;
- adding credential-heavy connectors as live scheduled sources;
- scaling Shopify/TikTok/Google Ads/PrestaShop beyond preview/concierge paths.

Acceptance reminders:

- required secret refs resolve at execution time without entering runtime hashes;
- Tiendanube/MercadoLibre/Meta Ads inline token paths are removed or explicitly isolated as compatibility shims with redaction tests;
- connector factory imports remain static/allowlisted;
- missing/invalid secrets produce redacted typed failures and open/update `data_stale` where integrated.

#### Packet U — Workflow action ledger and approval object foundation

Close before:

- any workflow automation that mutates cases durably;
- any external side effect;
- any action described to owners as executed or pending approval;
- self-service workflow rules.

Acceptance reminders:

- durable ledger records action key, case/work item ref, actor/source, idempotency key, approval state, execution state, timestamps, redacted params;
- duplicate idempotency keys are enforced against durable storage;
- approval-required actions create durable approval requests and cannot execute as side effects;
- existing dry-run projections remain backward-compatible.

### 3.3 Safe ordering principle

The safest order is:

1. Close security/secret/audit blockers that protect all future growth.
2. Deepen existing data/case value using current connectors.
3. Add one read-only connector at a time.
4. Add conversational read-only explanations.
5. Add observability/APM around canonical ledger/case state.
6. Only then move into durable actions, self-service onboarding, and external mutations.

This order prevents connector sprawl and agent UX from bypassing the platform primitives that make Orvo an operations control plane instead of a chatbot/reporting wrapper.

---

## 4. Recomendación: secuencia de crecimiento en goals acotados

This is a recommended sequence, not a feature mandate. Each goal should be its own branch/worktree and should stop at its exit criteria.

### Goal 1 — Close Packet O audit/RBAC live-use gate

**Capability:** make internal operator mutations/security trustworthy enough for future growth.

**Scope:** durable audit foundation for failed/denied actions, auth failures where context exists, route permission tests, redacted audit payloads.

**Exit criteria:**

- Packet O acceptance criteria pass.
- Viewer/operator/admin behavior is tested for read/mutate routes.
- No owner-facing feature changes are required.
- `pytest -q` passes.

### Goal 2 — Close Packet Q secret-ref execution gate

**Capability:** make connector execution safe for real credentials and future self-service.

**Scope:** runtime secret-ref resolution for current credentialed connectors, compatibility shims isolated, redacted typed failures, `data_stale` integration where available.

**Exit criteria:**

- Required secret refs resolve at execution boundary.
- Runtime hashes/compiled artifacts contain refs/digests only, never raw secrets.
- Tiendanube/MercadoLibre/Meta Ads tests cover missing/invalid credentials without leaks.
- `pytest -q` passes.

### Goal 3 — Product depth: strengthen `data_stale` and one existing D2C case family

**Capability:** improve client value without broad connector sprawl.

**Scope:** deepen `data_stale` remediation and choose one existing family (`stockout_risk`, `sales_drop`, or `fulfillment_backlog`) based on available evidence/freshness.

**Exit criteria:**

- New/updated cases cite registered metrics/evidence only.
- Owner/operator projections use registered action keys only.
- Stale-source suppression is tested.
- No new connector is required for the chosen family unless explicitly scoped.
- `pytest -q` passes.

### Goal 4 — Add one read-only commerce connector

**Capability:** broaden market while staying in familiar commerce metrics.

**Recommended candidates:** Shopify if strategic market reach wins; WooCommerce if implementation speed wins; PrestaShop only if a specific pilot requires it.

**Scope:** registry spec, read-only adapter, worker contract tests, runtime preview/forced/scheduled path, redacted failures, docs/example config. No self-service OAuth flow in this goal.

**Exit criteria:**

- Connector emits only declared metric families.
- Adapter follows worker pattern and allowlisted factory metadata.
- Credential errors are redacted and produce typed freshness/degraded behavior.
- Existing connectors remain green.
- `pytest -q` passes.

### Goal 5 — Read-only conversational case explanations

**Capability:** make Orvo feel interactive without letting conversation mutate truth.

**Scope:** owner/operator can ask why a case exists; response is generated from case evidence snapshots, action catalog, and current status. No status change, no external action, no hidden mutation.

**Exit criteria:**

- Explanations quote/cite existing evidence refs only.
- No invented numbers/action keys.
- Conversation layer does not import/own Brain state directly beyond approved service calls.
- Tests prove stale/degraded caveats are preserved.
- `pytest -q` passes.

### Goal 6 — Observability/APM v1 for multi-client operations

**Capability:** see run health, connector degradation, stale data, delivery status, and case mutations at operator scale.

**Scope:** read-only health summaries from run ledger/case stores; counters/log fields for run status and connector failure class; runbook for alerts. No new source of truth.

**Exit criteria:**

- Health view answers: what ran, which connector failed/staled, which cases changed, what was delivered/skipped.
- Dashboards/projections redact secrets and respect tenant/business scope.
- Logs/metrics include correlation IDs/run IDs.
- `pytest -q` passes.

### Goal 7 — Packet U durable action ledger and approval foundation

**Capability:** prepare for governed mutations without executing external side effects.

**Scope:** durable action ledger, approval object lifecycle, idempotency enforcement, manual mutation linkage. Keep workflow automation projection-only until the full gate is green.

**Exit criteria:**

- Packet U acceptance criteria pass.
- Duplicate idempotency keys are rejected/recognized durably.
- Approval-required actions cannot execute as side effects.
- Existing dry-run workflow projections remain backward-compatible.
- `pytest -q` passes.

### Goal 8 — Multi-client onboarding v0, still constrained

**Capability:** move from concierge config edits toward controlled onboarding.

**Scope:** tenant/business inventory, connector readiness/preflight, onboarding status, secret-ref records. No broad billing/self-service SaaS yet.

**Exit criteria:**

- A new business can be configured through validated records without raw secrets in runtime artifacts.
- Tenant/business scope is explicit in every read/write.
- Audit captures onboarding/admin changes.
- One connector install/reconnect path is documented and test-covered.
- `pytest -q` passes.

### Goal 9 — First governed real mutation

**Capability:** prove the control plane can safely perform one real mutation.

**Scope:** one low-risk action behind Packet O + Packet U gates, approval required, idempotent, audited, reversible or harmless. Prefer internal case mutation before external API mutation.

**Exit criteria:**

- Action request -> approval -> execution -> audit/timeline lifecycle is durable.
- Duplicate execution is prevented.
- Failure is redacted, typed, and visible in operator surfaces.
- No external mutation unless explicitly chosen and separately approved.
- `pytest -q` passes.

---

## Final recommendation

Start with **Goal 1 (Packet O)** and **Goal 2 (Packet Q)** before major market expansion. They are not flashy, but they unlock every serious growth axis: more clients, more connectors, conversational follow-up, and workflow automation.

After those gates, the highest leverage product-growth path is usually:

1. deepen existing Operational Cases on current Tiendanube/MercadoLibre/Meta data;
2. add one read-only commerce connector, likely Shopify or WooCommerce depending on target pilots;
3. add read-only conversational explanations;
4. add APM/health surfaces for operating multiple clients;
5. only then introduce durable action approvals and governed mutations.

Do not start broad external workflow automation, self-service onboarding, or many connectors in parallel until audit, secret-ref execution, and action-ledger foundations are green.

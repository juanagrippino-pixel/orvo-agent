# Orvo Capacity + Control Plane Deep Research

> **For Hermes:** use this memo as the next-wave synthesis after Phase A foundations were integrated. It translates the new structure into higher-leverage product, architecture, and autonomous-execution tracks.

**Date:** 2026-05-24  
**Repo state during research:** `/root/orvo-agent`, branch `feat/configurable-insight-thresholds`, clean, `360 passed` after Phase A integration.  
**Phase A foundations now present:** ADRs/architecture contract, connector registry, compiled runtime scaffold, run ledger foundation.

---

## Executive thesis

Orvo should not become “more reports”. The new structure makes Orvo capable of becoming an ecommerce operations control plane:

```text
WhatsApp report
  -> Operational Cases
  -> exception queue / daily ops cockpit
  -> owner approvals
  -> playbooks
  -> controlled automations
  -> benchmarks and reusable ops intelligence
```

The WhatsApp 8:00 report remains the wedge and trust habit. The product underneath should become a deterministic, auditable control plane for Tiendanube-first D2C physical-goods ecommerce in Argentina/LatAm.

---

## External patterns worth copying structurally

Do not copy surface complexity. Copy the primitives.

### Atlassian / Jira-like platform primitives

Useful pattern:
- native work object: Jira issue -> Orvo `OperationalCase`
- transitions/statuses/comments/actions
- automation rules around issue events
- platform extensibility through apps/Forge-like model
- centralized permission/audit boundaries

Relevant docs checked:
- Atlassian Forge: https://developer.atlassian.com/platform/forge/
- Jira issue REST API: https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/
- Jira automation actions: https://support.atlassian.com/cloud-automation/docs/jira-automation-actions/

Orvo interpretation:
- `OperationalCase` is the native object.
- Reports, WhatsApp messages, queues, timelines, and automations are projections/actions around cases.
- Case lifecycle and action audit become the durable product value.

### Shopify / ecommerce admin primitives

Useful pattern:
- Admin API as operator/control surface
- webhooks/events for operational state changes
- apps attach workflows to commerce objects

Relevant docs checked:
- Shopify Admin API: https://shopify.dev/docs/api/admin
- Shopify webhooks: https://shopify.dev/docs/api/admin-rest/latest/resources/webhook

Orvo interpretation:
- Tiendanube/MercadoLibre remain source of truth for orders/products/stock.
- Orvo becomes source of truth for coordination, exceptions, owner decisions, and audit history.
- Future webhooks can reduce polling, but first runtime/ledger/case invariants matter more.

### Zapier / n8n-like automation primitives

Useful pattern:
- triggers, actions, auth, rate limits, retries, connection health
- connector/app registry as product primitive

Relevant docs checked:
- Zapier Platform: https://platform.zapier.com/

Orvo interpretation:
- `ConnectorSpec` should become more than metadata: executor, health, scopes, rate limits, modes, validation, and action support.
- Automation should start human-in-the-loop, not full autonomy.

### Temporal / workflow-runtime primitives

Useful pattern:
- durable workflows
- retries/timeouts
- replayability/history
- deterministic execution constraints

Relevant docs checked:
- Temporal docs: https://docs.temporal.io/

Orvo interpretation:
- The current `RunLedger` is a lightweight first step toward replayable run history.
- Before introducing a heavy workflow engine, make forced/scheduled/preview runs share one compiled runtime and ledger writes.

### OpenTelemetry / observability primitives

Useful pattern:
- traces, metrics, logs, attributes, context propagation

Relevant docs checked:
- OpenTelemetry docs: https://opentelemetry.io/docs/

Orvo interpretation:
- A `run_id` should thread through connector execution, insights, report artifacts, dispatch, and case updates.
- Operator answers should be easy: what ran, what failed, what was degraded, why did/didn’t it send?

### LatAm connector ecosystems

Relevant docs checked:
- Tiendanube/Nuvemshop API: https://tiendanube.github.io/api-documentation/
- Mercado Libre Developers: https://developers.mercadolibre.com.ar/es_ar/api-docs-es
- Meta Marketing APIs: https://developers.facebook.com/docs/marketing-apis/

Orvo interpretation:
- Keep Tiendanube first.
- Mercado Libre and Meta Ads are high-value correlation connectors.
- Secrets, scopes, rate limits, and degraded-mode health must be productized in the registry before scaling clients.

---

## Repo-grounded findings

Current Orvo Brain surface:

- Core modules under `app/brain/`:
  - `models.py`, `config.py`, `insights.py`, `reporting.py`, `pipeline.py`, `runner.py`, `scheduler.py`, `storage.py`, `dispatch.py`, `delivery.py`
  - new: `connector_registry.py`, `runtime.py`, `run_ledger.py`
- Connectors under `app/brain/adapters/`:
  - CSV, Google Sheets, sample/manual, Tiendanube, MercadoLibre, Meta Ads
- Tests:
  - 27 brain/runtime script test files
  - full suite after Phase A integration: `360 passed`
- Size inspected with `pygount`:
  - 71 Python files, 7,226 code lines
  - 18 Markdown files, 3,041 comment/doc lines

Key gaps:

1. `runtime.py` and `connector_registry.py` are both present but not yet unified.
   - `runtime.py` still has `_CONNECTOR_DESCRIPTORS`.
   - Registry has richer `ConnectorSpec`, secret refs, executor metadata, health/rate/scope/lifecycle.

2. `CompiledBusinessRuntime` exists but is not the execution input yet.
   - forced CLI, scheduled runner, previews still use older paths.

3. `RunLedger` exists but is not wired into production runs.
   - it should record run start/end, connector outcomes, artifact refs, dispatch outcomes, degraded state, and errors.

4. Forced vs scheduled parity is still a high-risk boundary.
   - forced historically used one connector; scheduled can run multi-connector.

5. Metric semantics are not formalized.
   - adapters emit generic keys like `revenue_today` and `orders_today` while cross-channel insights want namespaced keys such as Tiendanube vs MercadoLibre revenue/orders.

6. Operational cases are architectural truth but not code yet.
   - `ArtifactRef.operational_case_ids` exists, but no `OperationalCase` model/store/engine exists.

---

## What the new structure can be used for immediately

### 1. Runtime parity engine

Use compiled runtime as the single executable plan for:
- preview
- forced/manual CLI
- scheduled runs

First implementation should be a compatibility shim over existing pipeline functions, not a rewrite.

Acceptance:
- same business/date/config yields same report shape across forced and scheduled paths
- `compile_business_runtime` consumes connector registry
- raw secrets do not leak into operator-visible runtime previews

### 2. Run history and operator audit

Use `RunLedger` to answer:
- Did the 8:00 report run?
- Which connectors ran?
- What was degraded?
- Did WhatsApp send or skip duplicate?
- What artifact/report was produced?
- What cases did it open/update?

First slice:
- optional ledger param in runner/forced CLI
- in-memory for tests, SQLite for runtime
- redaction invariants for tokens/errors/URIs

### 3. Connector self-service readiness

Use `ConnectorSpec` as the basis for:
- onboarding checklist
- missing secret refs
- connector health/degraded status
- rate-limit policy
- scope/permission display
- future executor routing

First slice:
- compile preview that returns structured validation issues
- no raw access tokens in operator-facing outputs

### 4. Metric registry and semantic validation

Use a metric registry to prevent semantic drift:
- metric key
- namespace/channel
- unit
- family
- evidence source
- aggregation semantics
- report/case participation
- deprecation/alias metadata

First slice:
- add registry without changing report output
- register legacy keys + desired namespaced keys
- tests prove adapters/insights/reporting use registered semantics

### 5. Operational Case engine

Use insights as inputs to case candidates:
- create/update/dedupe cases
- lifecycle: open, acknowledged, in_progress, resolved, reopened, dismissed
- evidence refs and timeline
- future WhatsApp projections

First slice:
- Pydantic models
- in-memory store
- deterministic dedupe from current `Insight`
- no WhatsApp behavior change yet

### 6. Operator API / cockpit

Use runtime + registry + ledger + cases to build internal operator endpoints:
- compile business runtime
- force run
- list run history
- inspect run detail
- list connector readiness
- list open cases

First slice must include auth/tenant/audit scaffolding before live use.

---

## High-value product use cases unlocked

### Tiendanube-first exception management

Prioritized case types:
- stockout risk on top sellers
- product promoted with low/no stock
- revenue/order drop vs baseline
- payment/checkout anomaly
- fulfillment backlog
- data stale/degraded connector

Commercial value:
- turns Orvo from report into operational risk detector
- creates repeatable ROI narrative

### Cross-system correlations

High-value correlations:
- Meta Ads spend active + Tiendanube orders down
- Meta Ads spend active + stock low/no stock
- WhatsApp purchase conversations up + orders flat
- Tiendanube down while MercadoLibre stable
- stock risk + customer demand signals

Commercial value:
- Orvo sees across systems that individual platforms do not connect
- strongest reason to expand connectors and pricing

### Owner approvals over WhatsApp

Examples:
- approve/dismiss/snooze case
- approve reminder/follow-up
- approve pause recommendation before action execution

Commercial value:
- WhatsApp becomes decision surface, not only report surface
- gathers feedback signal for future automation

### Playbooks per case type

Examples:
- `stockout_risk`: confirm stock, check ads, offer substitute, resolve/reopen
- `spend_without_orders`: check checkout, campaign links, stock, payment status, escalate if repeated

Commercial value:
- productizes operational know-how
- reduces reliance on manual concierge expertise

### Weekly ROI / operator review

Summary:
- cases opened/resolved/reopened
- recurrent issues
- degraded connector days
- actions approved/dismissed
- conservative impact estimate

Commercial value:
- retention and upsell proof

---

## Autonomous capacity model

Hermes capacity is already high:
- default: `openai-codex / gpt-5.5`, high reasoning
- delegation: up to 8 concurrent children, spawn depth 2
- Claude Code CLI available at `/root/.hermes/node/bin/claude`
- multiple Hermes profiles exist: backend/reviewer/researcher/integrator/ops
- existing crons/watchdogs already run Orvo loops

Recommended fleet:

```text
1 controller: gpt-5.5 high
3-4 Claude Code CLI coding workers: routine scoped implementation
2 gpt-5.5 reviewers: architecture/security/invariant review
1 gpt-5.5 integrator: sequential merges/tests
1 no-agent hygiene watchdog: dirty repo/worktree/cron checks
```

Use Claude CLI for routine coding via the Claude plan. Use gpt-5.5 high for orchestration, review, integration, hard debugging, and synthesis. Avoid Qwen/Kimi/cheap models and Anthropic API direct spend.

Hard rules:
- parent repo `/root/orvo-agent` stays clean
- autonomous workers use `/root/orvo-agent-worktrees/<slug>`
- one worker owns one branch/worktree
- merge one branch at a time
- run tests after each merge
- worker success reports are untrusted until diff/tests are verified

---

## Recommended next wave

### Wave 1 — make Phase A executable

1. Runtime consumes connector registry.
2. Runtime separates public params from secret refs.
3. Add compiled-runtime execution shim.
4. Forced CLI uses compiled runtime and multi-connector parity.
5. Scheduled runner uses same compiled execution function.
6. Run ledger wraps forced/scheduled execution.

### Wave 2 — semantics and cases

1. Metric registry scaffold.
2. Adapter/insight semantic validation.
3. OperationalCase models/store.
4. Case engine from current insights.
5. Run ledger artifact refs link to case IDs.

### Wave 3 — operator surface and action loop

1. Internal operator API for compile/run/history/cases.
2. Daily ops cockpit internal.
3. WhatsApp approve/dismiss/snooze.
4. Playbook/action records.
5. Controlled automations with explicit approvals.

### Wave 4 — scale intelligence

1. Cross-client anonymized baselines.
2. Weekly ROI summaries.
3. Connector health history.
4. Replay/evaluation harness for reports/cases.
5. Synthetic D2C data generator for regression tests.

---

## Immediate worker backlog

### Track A — registry/runtime unification

Scope:
- `app/brain/runtime.py`
- `app/brain/connector_registry.py`
- `tests/test_brain_runtime.py`
- `tests/test_brain_connector_registry.py`

Goal:
- remove duplicated connector descriptors
- compile from `ConnectorSpec`
- support secret refs safely

### Track B — forced/scheduled parity

Scope:
- `scripts/run_orvo_brain_reports.py`
- `app/brain/runner.py`
- `app/brain/pipeline.py`
- new parity tests

Goal:
- one compiled runtime execution function
- forced and scheduled execute the same connector plan

### Track C — run ledger integration

Scope:
- `app/brain/run_ledger.py`
- `app/brain/runner.py`
- `app/brain/dispatch.py`
- `scripts/run_orvo_brain_reports.py`
- integration tests

Goal:
- record runs, connector outcomes, artifact refs, dispatch outcomes
- keep current dispatch idempotency behavior

### Track D — metric registry scaffold

Scope:
- new `app/brain/semantics/metric_registry.py`
- adapters/insights/reporting tests

Goal:
- define metric semantics without breaking legacy output
- prepare namespaced channel metrics

### Track E — OperationalCase v0

Scope:
- new `app/brain/cases/`
- models/store/engine tests

Goal:
- cases from current insights
- deterministic dedupe/reopen semantics
- no WhatsApp behavior change yet

### Track F — operator API skeleton

Scope:
- `server.py` or new operator API module
- runtime/ledger integration
- auth/tenant/audit scaffolding tests

Goal:
- internal endpoints for compile preview, force run, run history, case list

---

## Priority rule

Hito 0 remains the first trust milestone. If there is a conflict between platform architecture and first real ARTEMEA 8:00 WhatsApp report, Hito 0 wins. But once Hito 0 is stable, the aggressive path is not more reports — it is case-native control plane execution.

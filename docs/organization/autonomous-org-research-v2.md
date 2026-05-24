# Orvo Autonomous Organization Research Marathon v2

> **Supersession note (2026-05-24):** This report was produced from an older prompt and still contains Hito/report-first framing. That framing is superseded. Orvo is now being operated as a sellable Atlassian-like ecommerce operations control plane. Read `docs/organization/product-pivot-correction.md` before using this report; keep the market/control-plane research, but reject any priority ordering that centers Hito 0 or a single WhatsApp report.

Date: 2026-05-24
Branch/worktree: `org/autonomous-org-research-v2` at `/root/orvo-agent-worktrees/autonomous-org-research-v2`
Scope: research and synthesis only; no cron creation, no push, no deploy.

## Executive thesis

Orvo should not be framed as a WhatsApp bot, BI dashboard, helpdesk, ERP, or generic AI agent. The durable product thesis is:

> Orvo is the deterministic, WhatsApp-first operations control plane for LatAm physical-goods ecommerce teams selling through Tiendanube, MercadoLibre, WhatsApp, carriers, ad channels, and ERP-lite systems.

Hito 0 remains the immediate trust wedge: a real 08:00 Argentina WhatsApp report to ARTEMEA/client-zero, in a dry non-AI operator tone, with evidence-backed numbers and no hallucinated recommendations. Hito 0 is not the destination; it is the first daily habit that proves the control plane deserves to exist.

The destination is case-native operations:

```text
External systems
  -> connector registry + validated execution plan
  -> semantic metric/event registry + evidence
  -> deterministic insight/case detection
  -> OperationalCase / WorkItem lifecycle
  -> run ledger + audit/replay
  -> operator surfaces: WhatsApp, API, queue, timeline
  -> rules, approvals, playbooks, controlled automations
```

Market research supports this direction. Argentine/LatAm ecommerce operators already run fragmented daily workflows across sales, fulfillment, payments, stock, shipping, marketplaces, customer conversations, ads, and invoicing. WhatsApp is an operating surface, not merely a marketing channel. Competitors either own analytics, helpdesk, ERP, shipping, marketplace sync, or WhatsApp marketing; the gap is deterministic exception management and team coordination across all of them.

The next build should therefore be dual-track:

1. Hito 0 trust path: make the 08:00 ARTEMEA report reliable, dry, audited, idempotent, and parity-safe.
2. Control-plane foundation: unify runtime/registry/ledger/semantic/case primitives so the report becomes a projection of operational state, not a one-off output.

## Research streams covered

1. LatAm/Tiendanube/D2C ecommerce owner workflows and pains.
2. WhatsApp-first operations and reporting habits.
3. Competitors and adjacent patterns: Shopify apps, Triple Whale/Northbeam, helpdesk, MercadoLibre tools, ERP-lite.
4. Control-plane architecture: connector registry, run ledger, semantic metrics, OperationalCase, operator APIs, audit/replay.
5. Autonomous organization design: departments, cadence, gates, escalation, integration, review, memory/docs.
6. QA/evals: golden reports, degraded data, timezone, delivery, connector drift, metric drift, tone regression.
7. Engineering roadmap: 24h, 72h, 7d, 30d.

## Source-backed market findings

### LatAm/Tiendanube owner workflow pains

1. Ecommerce volume is large enough that owners need exception control, not just dashboards. CACE reports Argentina ecommerce at ARS 34.033.238 millones, 253M orders, 645M units, and an average ticket of ARS 134.519 in its 2025 annual study.
2. Fulfillment/shipping is a daily operating pain: package preparation, label printing, pickup requests, tracking, delay/damage/lost-package incidents, and customer WISMO questions.
3. Payments are fragmented and cashflow-sensitive: cards, wallet transfers, installments, payment gateways, rejected/pending payments, and settlement delays.
4. WhatsApp is a first-class sales/support channel. Tiendanube reports that 71.5% of Argentine entrepreneurs used WhatsApp as a sales channel in 2025.
5. Stock/inventory is a recurring risk, especially across Tiendanube + MercadoLibre + spreadsheets/ERP. Owners need oversell/stockout prevention more than more charts.
6. Marketplace selling adds reputation pressure: MercadoLibre questions, claims, shipping promises, publication quality, stock sync, and cancellations become operational risks.
7. The Tiendanube owner workflow is fragmented across help sections for ventas, productos, medios de pago, envíos/locales, carritos abandonados, WhatsApp, and apps.

Implication: Orvo’s first useful unit is not “insight”. It is “what must be handled before the day starts.”

### WhatsApp-first reporting habits

WhatsApp should be treated as an interruptive operational channel. The 08:00 report should feel like a handoff from an operator, not a dashboard export or AI digest.

What belongs in WhatsApp:

- compact state of the day;
- blockers and exceptions;
- paid/unfulfilled orders;
- payment pending/rejected counts;
- stock/oversell risk;
- shipping issues/no movement/no tracking;
- unanswered customer/WhatsApp conversations;
- one priority action;
- data-health/source footer;
- links to details only when needed.

What does not belong:

- long tables;
- raw PII;
- every order line;
- generic BI commentary;
- motivational AI phrasing;
- unsupported causal claims;
- frequent low-value alerts;
- customer-facing copy mixed with internal ops.

Hito 0 recommended shape:

```text
ARTEMEA · 2026-05-24
Priority: clear aged orders before pushing more volume.

9 paid orders are still unprepared. 2 have no confirmed stock.
- Revenue yesterday: ARS X
- Pending payments: Y
- Shipping labels pending: Z

Sources: Tiendanube, Meta Ads. Inventory stale since 06:10; stock advice omitted.
```

## Competitor and adjacent pattern synthesis

### Analytics / attribution

Triple Whale, Northbeam, Polar Analytics, Lifetimely, and BeProfit sell source-of-truth analytics, attribution, profitability, and KPI clarity. They are useful references for confidence, normalization, and source-backed metrics, but they are not the right direct product shape. Orvo should borrow “source of truth” language and apply it to operational state: orders, payments, stock, shipping, conversations, exceptions, cases, and actions.

### Shopify operations apps

AfterShip, ShipStation, Stocky, Inventory Planner, ShipHero, MESA, and Mechanic show the modular Shopify pattern: one app for tracking, one for shipping, one for inventory, one for automation, one for reporting. This creates power but also app sprawl. Orvo’s LatAm/Tiendanube wedge can be less app sprawl, more control plane.

### Helpdesk and customer ops

Gorgias, Zendesk, Intercom/Fin, Re:amaze, Richpanel, DelightChat, and Zoko embed ecommerce context in support flows. Orvo should borrow the context-rich action pattern but avoid becoming another support queue. Its sharper lane is internal operations: “which orders are stuck?”, “what is likely to hurt reputation?”, “what should be approved?”, “what should be escalated?”

### MercadoLibre tools

MercadoLibre seller portals and APIs expose product publication, order management, questions/answers, shipping, invoicing, ads, and reputation-sensitive workflows. Nubimetrics, Real Trends, Astroselling, BaseLinker, Producteca, and EcomNube show demand for marketplace intelligence and sync. Orvo’s gap: post-sale exception orchestration across MercadoLibre + Tiendanube + WhatsApp + ERP/shipping.

### Tiendanube and LatAm ERP-lite ecosystem

Tiendanube apps include Dux Software ERP, EcommApp, TFactura, Facturante, Contagram, Envia, Zipnova, Whatsplaid GPT, Zoe, Alerti, and Revie. ERP-lite products such as Alegra, Contabilium, Siigo, Bling, Tiny/Olist Tiny, and Odoo own fiscal/accounting/inventory primitives. Orvo should integrate with them, not replace them.

Competitive frame:

> Orvo is not another BI dashboard, ERP, helpdesk, or WhatsApp chatbot. It is the deterministic WhatsApp-first operations control plane for LatAm ecommerce teams.

## Ranked product/platform opportunities

Ranked by urgency, Hito 0 trust impact, platform leverage, and sellability.

1. Real ARTEMEA 08:00 WhatsApp report
   - Why: first customer trust milestone and habit test.
   - Paths: `app/brain/reporting.py`, `app/brain/bootstrap.py`, `app/brain/scheduler.py`, `scripts/run_orvo_brain_reports.py`, `docs/product/report-design.md`.

2. Dry operator report renderer
   - Why: current renderer/test expectations are still closer to branded emoji dashboard output than Hito 0 operator tone.
   - Paths: `app/brain/reporting.py`, `tests/test_brain_reporting.py`, `tests/fixtures/orvo_brain/golden/*`.

3. Golden ARTEMEA report fixtures
   - Why: locks normal/critical/degraded outputs before real delivery.
   - Paths: `tests/test_brain_golden_reports.py`, `tests/fixtures/orvo_brain/golden/`.

4. Forced vs scheduled parity
   - Why: manual rehearsal must match scheduled 08:00 behavior; current forced path risk is first-enabled-connector-only.
   - Paths: `scripts/run_orvo_brain_reports.py`, `app/brain/runner.py`, `app/brain/pipeline.py`.

5. Run ledger wired into real runs
   - Why: Orvo must answer “did it run, what happened, did WhatsApp send?”
   - Paths: `app/brain/run_ledger.py`, `app/brain/runner.py`, `app/brain/dispatch.py`, `scripts/run_orvo_brain_reports.py`.

6. Connector registry as execution source of truth
   - Why: prevents scattered connector behavior and enables control-plane validation.
   - Paths: `app/brain/connector_registry.py`, `app/brain/runtime.py`, `app/brain/pipeline.py`.

7. CompiledBusinessRuntime unification
   - Why: one immutable executable plan for preview, forced, scheduled, and operator-triggered runs.
   - Paths: `app/brain/runtime.py`, future `app/brain/runtime/execution.py`, `tests/test_brain_runtime.py`.

8. Source health / degraded data model
   - Why: partial data must be explicit before advice; one connector failure should not create false calm.
   - Paths: `app/brain/models.py` additive fields or pipeline result wrapper, `app/brain/pipeline.py`, `app/brain/reporting.py`.

9. Metric registry v0 with legacy aliases
   - Why: prevents Tiendanube/MercadoLibre generic metric collisions and report/insight drift.
   - Paths: `app/brain/semantics/metric_registry.py`, `app/brain/insights.py`, `app/brain/reporting.py`, adapter tests.

10. Connector drift contract tests
    - Why: runner, preview, forced CLI, adapters, and registry must agree on params, evidence, supported modes, and errors.
    - Paths: `tests/contracts/test_connector_contracts.py`, `tests/test_brain_connector_registry.py`.

11. Delivery/idempotency red-team tests
    - Why: duplicate sends, failed sends, wrong recipient, and malformed provider responses are Hito 0 trust killers.
    - Paths: `app/brain/dispatch.py`, `app/brain/delivery.py`, `tests/test_brain_dispatch.py`, `tests/test_brain_delivery.py`.

12. Timezone and 08:00 docs/code alignment
    - Why: code appears aligned to `0 8 * * *`; docs still mention `0 9 * * *` in one place.
    - Paths: `app/brain/bootstrap.py`, `app/brain/scheduler.py`, `docs/orvo-brain-runtime.md`, `tests/test_brain_scheduler.py`.

13. Tone regression linter
    - Why: prevents AI-sounding drift even when numbers are right.
    - Paths: `tests/helpers/report_contract.py`, `tests/test_brain_golden_reports.py`.

14. OperationalCase v0 models/store/engine
    - Why: native product object; reports become projections, not the system of record.
    - Paths: `app/brain/cases/models.py`, `app/brain/cases/engine.py`, `app/brain/cases/storage.py`, `tests/test_brain_cases.py`.

15. Insight-to-case deterministic mapper
    - Why: bridges current deterministic insights to case-native product value.
    - Paths: `app/brain/cases/mapper.py`, `app/brain/insights.py`, `tests/test_brain_cases.py`.

16. Case dedupe/reopen semantics
    - Why: avoids noisy duplicate daily alerts and supports durable workflow.
    - Paths: `app/brain/cases/engine.py`, `app/brain/cases/storage.py`.

17. Case timeline projection
    - Why: sellable operator experience around what happened and who acted.
    - Paths: `app/brain/cases/projections.py`, future `app/brain/operator_api/*`.

18. Internal operator API skeleton
    - Why: compile preview, readiness, force dry run, run history, and open cases need a controlled internal surface.
    - Paths: `app/brain/operator_api/*` or carefully mounted `server.py` routes.

19. Connector readiness endpoint/model
    - Why: self-service onboarding and Hito 0 preflight require clear missing params/secrets/health.
    - Paths: `app/brain/connector_registry.py`, `app/brain/runtime.py`, `app/brain/operator_api/*`.

20. Secret reference indirection
    - Why: compiled runtime/operator APIs must never expose raw tokens.
    - Paths: `app/brain/runtime_env.py`, `app/brain/config.py`, `app/brain/connector_registry.py`.

21. Replay harness for reports/cases
    - Why: deterministic platform claims require “same input -> same output”.
    - Paths: `tests/fixtures/orvo_brain/replay/*`, `tests/test_brain_replay.py`.

22. Run artifact references linked to cases
    - Why: every case/report must show evidence lineage.
    - Paths: `app/brain/run_ledger.py`, `app/brain/cases/*`.

23. WhatsApp internal commands after cases exist
    - Why: approve/dismiss/snooze/acknowledge can become strong habit loops, but only after audit/case model.
    - Paths: future `app/brain/surfaces/whatsapp/*`, `app/brain/cases/engine.py`.

24. Case queue projection
    - Why: “what is open now?” is the operational product, even if first surface is WhatsApp.
    - Paths: `app/brain/projections/case_queue.py`, `app/brain/cases/projections.py`.

25. Workflow rules MVP
    - Why: Atlassian-like automation primitive; triggers/conditions/actions with approvals.
    - Paths: `app/brain/workflows/rules.py`, `app/brain/workflows/engine.py`, `tests/contracts/test_workflow_rules_contract.py`.

26. Data freshness and stale-source policies
    - Why: stale stock or ads data can create dangerous advice.
    - Paths: `app/brain/connector_registry.py`, `app/brain/pipeline.py`, `app/brain/reporting.py`.

27. Cross-channel Tiendanube + MercadoLibre imbalance detection
    - Why: a strong LatAm-specific operational insight once metric registry exists.
    - Paths: `app/brain/insights.py`, `app/brain/semantics/metric_registry.py`.

28. Stockout risk with active ads
    - Why: immediate owner value; physical-goods pain with real cost.
    - Paths: `app/brain/insights.py`, future `app/brain/cases/mapper.py`.

29. Spend-without-orders case
    - Why: common actionable issue combining Meta Ads and commerce data.
    - Paths: `app/brain/insights.py`, `app/brain/cases/*`.

30. Shipping/no-movement exception model
    - Why: core D2C pain; becomes more important as carrier connectors mature.
    - Paths: future shipping adapters, `app/brain/semantics/*`, `app/brain/cases/*`.

31. Unanswered conversation backlog
    - Why: WhatsApp commerce means unanswered purchase/support chats have direct revenue and trust impact.
    - Paths: future WhatsApp/helpdesk adapters, `app/brain/semantics/*`, `app/brain/cases/*`.

32. Marketplace reputation risk cases
    - Why: MercadoLibre reputation pressure is LatAm-specific and valuable.
    - Paths: `app/brain/adapters/mercadolibre.py`, `app/brain/cases/*`.

33. Weekly operator review
    - Why: sellable retention artifact: cases opened/resolved/reopened, degraded days, actions approved/dismissed.
    - Paths: `app/brain/cases/projections.py`, `app/brain/reporting.py` or separate review renderer.

34. Lightweight ROI/impact estimates
    - Why: helps sales/retention; must be conservative and evidence-backed.
    - Paths: future `app/brain/product_metrics/*`, run ledger/cases.

35. Tiendanube-first onboarding checklist
    - Why: faster client onboarding; maps required connectors, credentials, schedules, WhatsApp destination, dry-run preflight.
    - Paths: `docs/orvo-brain-runtime.md`, `examples/*`, future operator API readiness.

36. Official MercadoLibre API path only
    - Why: avoid policy/gray-hat risk; use developer APIs and transparent seller flows.
    - Paths: `app/brain/adapters/mercadolibre.py`, connector registry docs.

37. ERP-lite integration strategy
    - Why: integrate with Dux/Contabilium/Alegra/etc. later; do not become ERP.
    - Paths: docs first, future connectors only after registry/ledger/semantics stabilize.

38. Product packaging: “Ops control plane for Tiendanube brands”
    - Why: clearer than “AI report”; sellable around exceptions, cases, evidence, WhatsApp habit.
    - Paths: `docs/product/*`, sales collateral later.

## Department-by-department responsibilities and next tasks

### Chief of Staff / COO

Responsibilities:
- Own priority stack and WIP limits.
- Keep Hito 0 visible while pushing control-plane architecture.
- Prevent overlapping workers on the same files.
- Convert broad goals into bounded tasks with allowed paths/tests.
- Enforce external worktrees and clean parent repo.

Next tasks:
- Maintain a live Hito 0 readiness score.
- Keep a single integration queue owned by Release/Integration.
- Assign every red/yellow risk in this report to a department.
- Stop tracks that do not produce durable artifacts or verified code/docs.

### Product & Market Intelligence

Responsibilities:
- Own ICP, customer workflows, product wedge, owner-facing value, tone, packaging.
- Translate LatAm/Tiendanube/WhatsApp research into specs.
- Prevent feature sprawl and generic AI positioning.

Next tasks:
- Freeze ARTEMEA Hito 0 acceptance criteria: required sections, forbidden claims, length, source footer, degraded behavior.
- Rank top 5 report improvements by customer trust impact.
- Produce a Spanish business glossary for metrics and case names.
- Define first sellable SKU: “ops control plane for Tiendanube brands.”

### Architecture Review Board

Responsibilities:
- Own control-plane vs runtime/data-plane boundaries.
- Approve changes touching runtime, registry, ledger, semantics, cases, operator API, dispatch/idempotency.
- Enforce no competing Alert/Task/Incident lifecycles outside `OperationalCase`.
- Keep LLMs out of calculations, detections, case decisions, degraded mode, dispatch decisions.

Next tasks:
- Turn Phase A architecture contract into an implementation dependency checklist.
- Block new surfaces until runtime/ledger/semantics/cases have minimal contracts.
- Require registry/runtime parity design before adding more connector branches.

### Engineering Factory Manager

Responsibilities:
- Convert approved specs into non-overlapping implementation worktrees.
- Define branch, worktree, allowed files, test command, expected artifact, non-goals.
- Keep heavy coding concurrency bounded and avoid central-file collisions.

Next tasks:
- Create bounded tasks for: Hito 0 renderer, forced/scheduled parity, run ledger integration, metric registry shim, golden reports.
- Keep platform scaffolds additive until Hito 0 path is safe.
- Require focused tests and commit SHA from each worker.

### QA / Red Team Director

Responsibilities:
- Own golden tests, degraded data tests, tone regression, connector drift, metric drift, delivery/idempotency red-team.
- Verify worker self-reports against diffs/tests.
- Protect against unsupported claims and false zeroes.

Next tasks:
- Add golden ARTEMEA report fixture plan.
- Add tone linter with banned AI/consultant phrases.
- Add delivery duplicate/failure/wrong-recipient tests.
- Add metric drift guard for Tiendanube/MercadoLibre revenue/order keys.

### Release / Integration Manager

Responsibilities:
- Inventory branches/worktrees and classify readiness.
- Verify commits, changed files, tests, Hito 0 impact, rollback notes.
- Prepare integration order; do not push/deploy without human approval.

Next tasks:
- Produce release manifest template.
- Classify current Hito 0 and Phase A branches as ready/stale/conflict-risk/needs review.
- Sequence Hito 0 trust branches before platform expansion branches.

### SRE / Operations Director

Responsibilities:
- Own runtime health, preflight, logs, delivery risk, repo hygiene, redaction, operational runbooks.
- Track 08:00 Argentina readiness without creating cron jobs in this wave.

Next tasks:
- Document Hito 0 operational preflight: config, schedule, dry-run, connector readiness, WhatsApp destination, idempotency state, logs/artifacts, fallback.
- Resolve docs/code 08:00 vs 09:00 drift.
- Recommend timeout/retry/degraded-mode policies for Tiendanube, Meta Ads, WhatsApp.

### Knowledge / Roadmap Librarian

Responsibilities:
- Keep docs, ADRs, roadmap, source-of-truth index, and worker handoffs coherent.
- Prevent stale plans from becoming hidden truth.
- Turn worker outputs into durable docs only after validation.

Next tasks:
- Index operating plan, Phase A architecture contract, ADRs, Hito 0 specs, runtime docs, worktree hygiene, product/report specs.
- Reconcile Hito-first vs product-control-plane language: Hito 0 is priority wedge; cases/control plane is destination.
- Maintain Now/Next/Later/Deferred roadmap.

### Board Report

Responsibilities:
- Give Juan concise evidence-backed executive status.
- Surface only real decisions: merge, push, deploy, credentials, customer action, product trade-off, external Hito 0 info.

Next tasks:
- Fixed report shape: Hito 0 status, verified branches/tests, blockers, risks, decisions needed, next 4-hour plan.
- Never claim “done” without branch/commit/test/doc evidence.

### Work Management Platform

Responsibilities:
- Own `OperationalCase` / `WorkItem`, lifecycle, transitions, comments, evidence, audit, dedupe/reopen, SLA/assignee/labels.

Next tasks:
- Draft `OperationalCase` v0 schema and lifecycle tests.
- Map current insights to case types without changing WhatsApp behavior.

### Connector Platform

Responsibilities:
- Own connector registry, contracts, capabilities, secret refs, health, scopes, rate limits, emitted metrics/events.

Next tasks:
- Make `app/brain/runtime.py` consume `ConnectorSpec` from `app/brain/connector_registry.py`.
- Add contract tests for required params, secret refs, modes, evidence source, and error redaction.

### Semantic Intelligence Platform

Responsibilities:
- Own metric/event definitions, aliases, units, evidence semantics, aggregation rules, missing-vs-zero behavior, insight-to-case semantics.

Next tasks:
- Add metric registry v0 for current and namespaced commerce/ads keys.
- Validate every emitted metric used by report/insight/case logic.

### Operator Experience / Surfaces

Responsibilities:
- Own WhatsApp, API, timeline, queue, and report projections around cases/runs. Surfaces are not source of truth.

Next tasks:
- Keep Hito 0 WhatsApp as plain text and dry.
- Design internal operator API only after auth/tenant/audit expectations are explicit.

### Platform Trust / Security / Admin

Responsibilities:
- Own tenant/workspace boundaries, RBAC, audit log, secret indirection, redaction, idempotency and operator-safe previews.

Next tasks:
- Define secret reference pattern and operator-safe runtime preview redaction rules.
- Add no-secret-leakage tests for ledger/runtime/operator surfaces.

## Implementation tracks with repo paths

### Track 0: Hito 0 ARTEMEA trust path

Goal: real deterministic 08:00 Argentina WhatsApp report with dry non-AI tone.

Paths:
- `app/brain/reporting.py`
- `tests/test_brain_reporting.py`
- `tests/test_brain_golden_reports.py`
- `tests/fixtures/orvo_brain/golden/`
- `app/brain/bootstrap.py`
- `app/brain/scheduler.py`
- `scripts/run_orvo_brain_reports.py`
- `docs/product/report-design.md`
- `docs/orvo-brain-runtime.md`

Acceptance:
- Option A-style report: `ARTEMEA · date`, `Priority: ...`, max 2-3 facts, source/data-health footer, no emoji by default.
- 08:00 ART schedule represented in tests/docs.
- Dry-run rehearsal is deterministic.
- No real send without explicit human confirmation.

### Track A: Registry/runtime unification

Paths:
- `app/brain/runtime.py`
- `app/brain/connector_registry.py`
- future `app/brain/runtime/execution.py`
- `tests/test_brain_runtime.py`
- `tests/test_brain_connector_registry.py`

Acceptance:
- `CompiledBusinessRuntime` consumes `ConnectorSpec`.
- No duplicate descriptor truth.
- Secret refs, not raw secret values, in compiled/operator-visible artifacts.

### Track B: Forced/scheduled parity

Paths:
- `scripts/run_orvo_brain_reports.py`
- `app/brain/runner.py`
- `app/brain/pipeline.py`
- `tests/test_run_orvo_brain_reports_script.py`
- new parity tests

Acceptance:
- Same business/date/config produces same merged report shape across forced and scheduled paths.
- Multi-connector config no longer silently degrades to first enabled connector in forced mode.

### Track C: Run ledger integration

Paths:
- `app/brain/run_ledger.py`
- `app/brain/storage.py`
- `app/brain/runner.py`
- `app/brain/pipeline.py`
- `app/brain/dispatch.py`
- `scripts/run_orvo_brain_reports.py`
- `tests/test_brain_run_ledger.py`

Acceptance:
- Run start/end, connector outcomes, artifact refs, dispatch outcomes, degraded status, and redacted errors recorded.
- Ledger answers Hito 0 audit questions.

### Track D: Metric registry and semantics

Paths:
- new `app/brain/semantics/metric_registry.py`
- `app/brain/insights.py`
- `app/brain/reporting.py`
- `app/brain/adapters/*.py`
- `tests/contracts/test_metric_registry_contract.py`
- `tests/test_brain_cross_channel_insights.py`

Acceptance:
- Every metric used for report/insight/case behavior is registered.
- Legacy aliases accepted while namespaced keys become canonical.
- Missing data is not silently zero.

### Track E: OperationalCase v0

Paths:
- new `app/brain/cases/models.py`
- new `app/brain/cases/engine.py`
- new `app/brain/cases/storage.py`
- new `app/brain/cases/projections.py`
- `tests/test_brain_cases.py`

Acceptance:
- Deterministic case creation, dedupe, priority, transitions, reopen.
- Cases link to evidence/run artifacts.
- No LLM case creation or prioritization.

### Track F: Operator API skeleton

Paths:
- new `app/brain/operator_api/*` or carefully mounted internal `server.py` routes
- `app/brain/runtime.py`
- `app/brain/run_ledger.py`
- future `app/brain/cases/*`
- `tests/test_server_brain*.py` or operator API tests

Acceptance:
- Internal-only endpoints for compile preview, connector readiness, force dry run, run history, run detail, open cases.
- Auth/tenant/audit scaffolding defined before live use.
- No raw secrets in responses.

### Track G: QA/eval harness

Paths:
- `tests/fixtures/orvo_brain/golden/`
- `tests/fixtures/orvo_brain/replay/`
- `tests/helpers/report_contract.py`
- `tests/test_brain_golden_reports.py`
- `tests/test_brain_delivery.py`
- `tests/contracts/*`

Acceptance:
- Golden report snapshots.
- Tone lint.
- Degraded data matrix.
- Delivery/idempotency tests.
- Connector/metric contract tests.
- Replay determinism tests.

## QA/evals and red-team findings

### Highest-risk failure modes

1. Hito 0 report sent at the wrong time because docs/config/schedule drift.
2. Report tone passes tests but sounds like AI/dashboard output.
3. One connector failure blocks all reporting or produces false calm.
4. Tiendanube/MercadoLibre generic keys collide and hide channel-specific issues.
5. Missing data is interpreted as zero.
6. Meta Ads currency mismatch produces invalid ROAS.
7. Duplicate scheduler run sends duplicate WhatsApp.
8. Provider timeout creates unknown delivery state with unsafe retry/idempotency behavior.
9. Wrong WhatsApp recipient due config error.
10. Logs/ledger/operator output leaks tokens or tokenized URLs.
11. Source labels or Sheet text inject prompt/tone instructions into report rendering.
12. Broad platform refactor breaks current Hito 0 path.

### Golden fixtures to add

- `artemea_normal_day.json`: no urgent issue, dry report under 700 chars.
- `artemea_revenue_drop.json`: revenue below baseline, ads active, checkout/payment priority.
- `artemea_stock_critical.json`: low stock, ads active, pause/hold action.
- `artemea_unanswered_chats.json`: support backlog high, reply-first priority.
- `artemea_spend_no_sales.json`: spend > 0, orders = 0, no invented cause.
- `artemea_multichannel_roas_low.json`: Tiendanube + MercadoLibre + Meta Ads; channel identity preserved.
- `artemea_partial_stock_stale.json`: stock advice omitted before recommendation.
- `artemea_connector_failure_partial.json`: partial report only if minimum trustworthy commerce source exists.
- `artemea_no_data_abort.json`: no owner report or explicit failure policy if no usable facts.

### Contract assertions

- Output deterministic for same fixture.
- Normal report <= 700 chars; critical <= 1100 chars.
- First or second line starts with `Priority:`.
- No banned phrases: “I think”, “I noticed”, “as an AI”, “based on my analysis”, “exciting insights”, “holistic”, “optimize your business performance”, unsupported “because customers...”.
- Every owner-facing metric has evidence.
- Partial/degraded state appears before advice.
- Sources footer matches actual available sources.
- Dry-run never calls real WhatsApp provider.
- Successful delivery marks idempotency; failed delivery does not.
- Duplicate after success skips provider call.
- Secrets are redacted from errors, ledgers, logs, docs, and operator responses.

## Roadmap

### Next 24 hours

Outcome: Hito 0 becomes ready for real ARTEMEA 08:00 rehearsal.

1. Freeze Hito 0 acceptance criteria from `docs/product/report-design.md` Option A.
2. Add golden report fixture plan and initial tests.
3. Align report renderer or add Hito0 renderer behind explicit use.
4. Verify/patch 08:00 ART docs/code/test alignment; do not create cron.
5. Add delivery duplicate/failure/wrong-recipient tests for current path.
6. Run dry-run rehearsal only when config is present; no real send without human confirmation.

### Next 72 hours

Outcome: Hito 0 remains shippable while Phase A becomes executable.

1. Make runtime consume connector registry.
2. Fix forced/scheduled parity.
3. Wire run ledger around forced/scheduled execution.
4. Add degraded/source-health model and report behavior.
5. Add metric registry shim with legacy aliases and test-mode validation.
6. Release one branch at a time with focused tests then `pytest -q`.

### Next 7 days

Outcome: Orvo becomes a deterministic control-plane base, not just a daily report path.

1. Metric registry v0.
2. OperationalCase v0 models/store/engine.
3. Insight-to-case deterministic mapper.
4. Internal operator API skeleton.
5. Connector health/degraded semantics.
6. Golden report + replay eval harness.
7. Case queue/timeline projection design.

### Next 30 days

Outcome: case-native ecommerce operations control plane for Tiendanube-first LatAm SMBs.

1. Reports become projections from cases + compact metrics.
2. WhatsApp decision loop: acknowledge, dismiss, snooze, approve; all audited.
3. Playbooks per case type: stockout, spend_without_orders, data_stale, shipping_delay, marketplace_reputation.
4. Tenant/secret/admin hardening.
5. Tiendanube + MercadoLibre + Meta Ads + WhatsApp operating loop.
6. Weekly operator review: cases opened/resolved/reopened, degraded connector days, actions approved/dismissed, conservative impact estimate.
7. GTM packaging around “ops control plane for Tiendanube brands.”

## Things NOT to build yet

- Do not build a full web cockpit before Hito 0, ledger, cases, and operator API contracts are stable.
- Do not add Temporal or heavyweight workflow infrastructure yet.
- Do not build a mini-ERP: no accounting, payroll, tax, full purchasing, POS, or general ledger.
- Do not compete head-on with Triple Whale/Northbeam on attribution/MMM.
- Do not add autonomous external actions such as pausing ads, changing stock, issuing refunds, canceling orders, modifying stores, or promising customers anything.
- Do not use LLMs to calculate metrics, create cases, rank cases, decide degraded mode, decide dispatch, or infer root causes.
- Do not add more connectors unless required for ARTEMEA or unless registry/runtime/ledger/semantics can support them.
- Do not expose mutable operator endpoints publicly before auth, tenancy, audit, idempotency, and rate limits exist.
- Do not rewrite `app/brain/models.py` or replace working modules with stubs.
- Do not create cron jobs, push, deploy, or send real WhatsApp messages without explicit approval.
- Do not let WhatsApp report copy become the strategic center; it is the first surface, not the product core.

## Sources and links

Market and ecommerce:
- CACE Argentina ecommerce statistics / Estudio Anual 2025: https://cace.org.ar/estadisticas/
- CACE annual study article: https://cace.org.ar/blogs/news/estudio-anual-de-cace-2025-el-ecommerce-como-canal-estructural-del-consumo-argentino
- Tiendanube NubeCommerce resources: https://site.tiendanube.com/recursos/nubecommerce
- Tiendanube sales category: https://ayuda.tiendanube.com/es_AR/ventas
- Tiendanube products category: https://ayuda.tiendanube.com/es_AR/productos
- Tiendanube payments category: https://ayuda.tiendanube.com/es_AR/medios-de-pago
- Tiendanube shipping category: https://ayuda.tiendanube.com/es_AR/envios-y-locales
- Tiendanube Envio Nube shipment management: https://ayuda.tiendanube.com/es_AR/envio-nube-gestion-de-envios
- Tiendanube Envio Nube tracking: https://ayuda.tiendanube.com/es_AR/envio-nube-seguimiento
- Tiendanube Envio Nube incidents: https://ayuda.tiendanube.com/es_AR/envio-nube-incidencias
- Tiendanube payment methods: https://www.tiendanube.com/blog/medios-de-pago/
- Tiendanube payment gateways: https://www.tiendanube.com/blog/pasarela-de-pago/
- Tiendanube stock in ecommerce: https://www.tiendanube.com/blog/como-funciona-el-stock-en-el-ecommerce/
- Tiendanube stock control system: https://www.tiendanube.com/blog/sistema-de-control-de-stock/
- Tiendanube WhatsApp selling: https://www.tiendanube.com/blog/como-vender-por-whatsapp/
- Tiendanube WhatsApp Business: https://www.tiendanube.com/blog/whatsapp-business/
- Tiendanube WhatsApp button help: https://ayuda.tiendanube.com/es_AR/123362-whatsapp/como-agregar-el-boton-de-whatsapp-en-mi-tiendanube
- Tiendanube Chat Nube + WhatsApp: https://ayuda.tiendanube.com/es_AR/configurar-tu-asistente/como-conectar-mi-asistente-virtual-a-whatsapp-para-que-empiece-a-responder
- Tiendanube abandoned carts: https://ayuda.tiendanube.com/es_AR/123339-carritos-abandonados/como-recuperar-los-carritos-abandonados
- Tiendanube MercadoLibre selling: https://www.tiendanube.com/blog/como-vender-en-mercado-libre/
- Tiendanube MercadoLibre publication quality: https://www.tiendanube.com/blog/mejorar-publicaciones-mercado-libre/
- Tiendanube marketplace vs ecommerce: https://www.tiendanube.com/blog/marketplace-vs-ecommerce/

WhatsApp and LatAm behavior:
- WhatsApp Business Platform: https://whatsappbusiness.com/products/business-platform/
- WhatsApp Business app listing: https://play.google.com/store/apps/details?id=com.whatsapp.w4b&hl=en
- DataReportal Digital 2025 Argentina: https://datareportal.com/reports/digital-2025-argentina
- Statista Argentina social network penetration: https://www.statista.com/statistics/284401/argentina-social-network-penetration/
- Greenbook on WhatsApp trust in LatAm: https://www.greenbook.org/insights/focus-on-latam/why-latin-american-consumers-trust-whatsapp-more-than-corporate-emails
- Techloy on WhatsApp Business and LatAm ecommerce: https://www.techloy.com/how-whatsapp-business-is-transforming-e-commerce-in-latin-america/
- Sherlock Communications WhatsApp commerce LatAm: https://sherlockcomms.com/whatsapp-commerce-in-latin-america/

Competitors and adjacent tools:
- Triple Whale: https://www.triplewhale.com/
- Northbeam: https://www.northbeam.io/
- Polar Analytics: https://www.polaranalytics.com/ and https://apps.shopify.com/polar-analytics
- Lifetimely: https://apps.shopify.com/lifetimely-lifetime-value-and-profit-analytics
- BeProfit: https://apps.shopify.com/beprofit-profit-tracker
- AfterShip: https://apps.shopify.com/aftership
- ShipStation: https://apps.shopify.com/shipstation
- Stocky: https://apps.shopify.com/stocky
- Inventory Planner: https://apps.shopify.com/inventory-planner
- ShipHero: https://apps.shopify.com/shiphero
- MESA: https://www.getmesa.com/ and https://apps.shopify.com/mesa
- Mechanic: https://mechanic.dev/ and https://apps.shopify.com/mechanic
- Gorgias: https://www.gorgias.com/
- Zendesk Shopify: https://apps.shopify.com/zendesk
- Intercom Fin: https://www.intercom.com/fin and https://apps.shopify.com/intercom
- Re:amaze: https://www.reamaze.com/ and https://apps.shopify.com/reamaze
- Richpanel: https://www.richpanel.com/
- DelightChat: https://www.delightchat.io/
- Zoko: https://www.zoko.io/

MercadoLibre and LatAm ecosystem:
- MercadoLibre Developers Argentina API docs: https://developers.mercadolibre.com.ar/es_ar/api-docs-es
- MercadoLibre products/publications API: https://developers.mercadolibre.com.ar/es_ar/publica-productos
- MercadoLibre sales/orders API: https://developers.mercadolibre.com.ar/es_ar/gestiona-ventas
- MercadoLibre questions/answers API: https://developers.mercadolibre.com.ar/es_ar/gestiona-preguntas-respuestas
- MercadoLibre shipping API: https://developers.mercadolibre.com.ar/es_ar/envios
- MercadoLibre invoicing API: https://developers.mercadolibre.com.ar/es_ar/facturacion
- Mercado Ads Argentina: https://ads.mercadolibre.com.ar/
- Nubimetrics: https://www.nubimetrics.com/
- Real Trends: https://www.real-trends.com/
- Astroselling: https://www.astroselling.com/es/ and https://www.tiendanube.com/tienda-aplicaciones-nube/astroselling
- BaseLinker Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/baselinker
- Producteca Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/producteca
- EcomNube 2: https://www.tiendanube.com/tienda-aplicaciones-nube/ecomexperts-ecomnube2
- Tiendanube app store: https://www.tiendanube.com/tienda-aplicaciones-nube
- Tiendanube gestión apps: https://www.tiendanube.com/tienda-aplicaciones-nube/categorias/gestion
- Tiendanube envíos apps: https://www.tiendanube.com/tienda-aplicaciones-nube/categorias/envios
- Dux Software ERP Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/dux-software-erp
- EcommApp Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/ecommapp
- TFactura Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/tango-factura
- Facturante Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/facturante
- Contagram Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/contagram
- Envia Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/envia-com
- Zipnova Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/zipnova-ar
- Whatsplaid GPT Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/whatsplaid-gpt
- Zoe Seller Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/zoe-seller
- Alerti Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/alerti-app
- Revie Tiendanube: https://www.tiendanube.com/tienda-aplicaciones-nube/revie
- Alegra: https://www.alegra.com/
- Contabilium Argentina: https://contabilium.com/ar/
- Siigo: https://www.siigo.com/
- Bling: https://www.bling.com.br/
- Tiny/Olist Tiny: https://www.tiny.com.br/
- Odoo Inventory: https://www.odoo.com/app/inventory

Repo-grounded sources:
- `docs/organization/autonomous-org-operating-plan.md`
- `docs/architecture/phase-a-control-plane-contract.md`
- `docs/product/report-design.md`
- `docs/plans/2026-05-24-orvo-control-plane-program.md`
- `docs/plans/2026-05-24-orvo-capacity-and-control-plane-research.md`
- `docs/adr/0001-control-plane-bounded-contexts-and-module-ownership.md`
- `docs/adr/0002-operational-case-native-issue-object.md`
- `docs/adr/0003-deterministic-detection-llm-explanation-boundary.md`
- `app/brain/runtime.py`
- `app/brain/connector_registry.py`
- `app/brain/run_ledger.py`
- `app/brain/reporting.py`
- `app/brain/runner.py`
- `app/brain/pipeline.py`
- `app/brain/dispatch.py`
- `app/brain/delivery.py`
- `app/brain/bootstrap.py`
- `app/brain/adapters/*`

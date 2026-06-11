# N2 Pro QA: operator console gaps for app-first PyME OS

Date: 2026-06-11  
Scope: compact QA review of operator-surface docs/tests for the app-first PyME operating console.  
Constraint observed: no production code touched; no secrets read or copied.

## Executive summary

The current repo has meaningful operator-surface scaffolding: internal case queue/detail/timeline/action routes, run history/detail, redaction at API boundaries, idempotency for case actions, and some route-auth invariants. However, the **MVP still feels closer to an inspected case/run API than a La Pyme-category operating-system home**.

The biggest actionable gaps are:

1. **OS snapshot is specified but not surfaced or tested.** Roadmap 4C asks for module-status lanes for sales/orders, stock/fulfillment, customer attention, ARCA/fiscal, and treasury/reporting. The current dashboard aggregates cases and run history but does not expose a module readiness/monitoring snapshot derived from connector/runtime/case state.
2. **Module readiness is under-specified in operator API tests.** The internal API contract names `compile-preview`, `connectors/readiness`, `runs/dry-run`, and `runs/force-dispatch`, but the inspected operator API tests focus on session, cases, run history, audit, and redaction. Those readiness/dry-run paths need tests before owner-facing readiness claims.
3. **Case UX/API coverage is stronger, but still missing OS-snapshot-critical behavior.** Existing tests cover queue views, case detail/timeline, manual actions, redaction, idempotency, and route auth. Missing tests should prove recurrence after resolution, deterministic priority ordering, evidence freshness gates, `data_stale`/setup-required cases, and owner-facing suppression when evidence is stale.
4. **WhatsApp-as-alerts-only needs explicit owner-brief invariants.** Docs repeatedly require WhatsApp to be a concise alert/projection channel, not the control surface. Tests should prove owner briefs cite actionable canonical cases only, exclude resolved cases, keep total counts truthful when truncated, avoid raw PII/message bodies, and never imply side effects from text.

## Sources checked

Docs/specs:

- `docs/README.md`
- `docs/adr/0005-d2c-ecommerce-wedge-platform-core.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/specs/d2c-operator-surface-contract.md`
- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/d2c-action-key-catalog.md`
- `docs/specs/internal-operator-api-contract.md`
- `docs/specs/operational-case-engine-contract.md`
- `docs/specs/connector-registry-contract.md`
- `docs/specs/compiled-runtime-contract.md`
- `docs/specs/metric-registry-contract.md`
- `docs/specs/tenant-secret-redaction-contract.md`
- `docs/specs/testing-invariant-matrix.md`
- `docs/roadmap/d2c-control-plane-roadmap.md`
- `docs/organization/d2c-autonomous-worker-addendum.md`

Tests inspected:

- `tests/test_operator_dashboard.py`
- `tests/test_operator_case_views.py`
- `tests/test_internal_operator_api.py`
- `tests/test_operator_case_actions.py`
- `tests/test_operator_run_projections.py`
- `tests/invariants/test_internal_operator_route_auth.py`

Implementation surfaces spot-checked for context only:

- `app/http/internal_brain/dashboard_views.py`
- `app/http/internal_brain/runs_delivery.py`
- `app/brain/operator_api/runs_dashboard.py`
- `app/brain/operator_api/projections.py`
- `app/brain/operator_views.py`
- `app/brain/work_items.py`

## What is already covered

### Case queue/detail/timeline

Existing tests cover much of the operator-case surface:

- built-in case views for actionable, degraded, recent, acknowledged, in-progress, and resolved-recent queues;
- case detail/timeline projections;
- redaction of actor/comment/metadata fields at projection boundaries;
- `release_state`, `status_category`, WorkItem envelope, priority bracket, and query-field metadata;
- route auth for internal operator endpoints;
- case actions with idempotency conflicts and audit/timeline behavior.

This is a good foundation for the internal case console, but it is not yet the OS home.

### Run history and redaction

Run history/detail tests and projection tests cover:

- run history/detail endpoints;
- redaction of connector secret refs and token-like URI values at the operator API boundary;
- dispatch status summary;
- `redaction_applied=true` in internal responses.

This supports operator inspection of run health, but the current run history projection is still ledger-oriented rather than module-readiness-oriented.

### Manual case actions

The action path is relatively well protected:

- registered action keys are enforced;
- manual case actions require idempotency;
- duplicate completed requests replay current case state;
- duplicate pending/failed keys are rejected;
- actor refs are normalized/redacted;
- denied/failed actions are audited.

## Gap 1 — OS snapshot / operator home

### Expected from docs

Roadmap 4C requires an operator home / OS snapshot showing module status for:

- sales/orders;
- stock/fulfillment;
- customer attention;
- ARCA/fiscal readiness;
- treasury/reporting readiness.

Exit criteria require the merchant to understand:

- what Orvo monitors today;
- what is stale;
- what needs connecting next;
- which owner-facing claims have evidence and source freshness.

### Current gap

The current dashboard is an aggregation of case queues and run history. It does not expose a module registry or module-state projection that answers:

- which modules are enabled, promoted, readiness-gated, deferred, or internal-only;
- which source connectors back each module;
- whether each module has fresh evidence;
- whether a module is blocked by missing credentials, stale data, or setup-required state;
- what next setup action the operator should take.

### Actionable tests to add

1. **OS snapshot contract test**
   - Given a business with Tiendanube OK, stock data stale, WhatsApp missing, ARCA not configured, and treasury/reporting legacy-only.
   - Assert module snapshot has exactly the expected module rows and statuses.
   - Assert owner-facing modules are only `promoted` when readiness gates pass.

2. **OS snapshot source-of-truth test**
   - Derive module status only from connector outcomes, run ledger, metric/evidence freshness, and cases.
   - Assert no marketing copy or hard-coded module status can create an owner-facing claim.

3. **OS snapshot UX test**
   - Snapshot response should include for each module: `module_key`, `label`, `readiness_state`, `source_connectors`, `last_evidence_at`, `blocking_case_ref`, `next_setup_action_key`, and `owner_facing_allowed`.

4. **Dashboard smoke/golden test**
   - Add a golden fixture for a healthy D2C business and a degraded D2C business.
   - Assert the OS snapshot appears before case queues in the operator home response.

## Gap 2 — module readiness and setup-required cases

### Expected from docs

Connector health taxonomy defines `ok`, `degraded`, `stale`, `unauthorized`, `rate_limited`, and `failed`. Stale/unauthorized states should suppress dependent advice and open/update `data_stale` or setup-required context.

### Current gap

The operator API contract names readiness surfaces, but the inspected tests do not cover:

- compile preview;
- connector readiness;
- dry-run run creation;
- force-dispatch approval/admin-only behavior;
- mapping from connector health to module readiness;
- deterministic creation/update of setup-required or `data_stale` cases.

### Actionable tests to add

1. **Compile preview endpoint test**
   - Does not execute connectors.
   - Redacts secret refs and validation errors.
   - Returns runtime/config hash and connector summary.

2. **Connector readiness endpoint test**
   - Returns registry validation, secret-ref presence, and last health state.
   - Redacts raw URLs/tokens.
   - Maps health states to owner-facing behavior.

3. **Dry-run ledger test**
   - Creates run ledger entries and artifacts.
   - Does not dispatch externally.
   - Marks secondary dispatch as skipped/no-op.

4. **Setup-required case test**
   - Missing connector or missing freshness gate opens/updates a deterministic setup-required or `data_stale` case.
   - Case title is redacted/safe.
   - Owner-facing copy can cite the case/evidence ref without exposing setup secrets.

## Gap 3 — cases: UX/API/test gaps beyond current coverage

### Current coverage

Existing case tests are strong for basic queue/detail/action behavior. They cover built-in views, redaction, idempotency, actor normalization, timeline persistence, and route auth.

### Missing coverage

The OS-snapshot direction needs stronger case behavior around evidence freshness, recurrence, and owner-facing readiness.

### Actionable tests to add

1. **Resolved recurrence test**
   - A resolved case should become actionable again when fresh evidence repeats the same dedupe condition.
   - Assert no duplicate case is created when the open case already exists.

2. **Priority ordering test**
   - Given mixed case types/priorities/freshness.
   - Assert deterministic ordering across queue, OS snapshot, and owner brief selection.

3. **Stale evidence suppression test**
   - When source connector is stale, dependent owner-facing claims are suppressed.
   - Assert `data_stale` or setup-required case is emitted instead of unsupported advice.

4. **Evidence freshness boundary test**
   - Owner-facing case detail/brief should include evidence freshness and source connector health.
   - Assert no claim is emitted without a non-stale evidence snapshot.

5. **Case title redaction test**
   - Case titles should be redacted at API and owner-brief boundaries.
   - This matters especially for customer attention/WhatsApp support cases.

6. **Open queue count truthfulness test**
   - When UI truncates displayed cases, the total open-case count must remain truthful.
   - This prevents the console from hiding operational load.

## Gap 4 — WhatsApp-as-alerts-only

### Expected from docs

The operator surface contract and roadmap require WhatsApp to remain a concise alert/projection channel. The operator console remains the canonical control surface. WhatsApp briefs should cite case/evidence refs and allowed action keys, but should not own workflow state.

### Current gap

Run projection tests prove redaction, but the inspected suite does not yet prove the owner-brief invariants needed to keep WhatsApp in its lane.

### Actionable tests to add

1. **Actionable cases only**
   - Owner brief should include only actionable/open canonical cases.
   - Resolved/dismissed cases must be excluded from the alert list.

2. **Truncation count truthfulness**
   - If `max_cases` hides lower-priority cases, the brief should still show the truthful total count.

3. **No raw PII/message bodies**
   - Support/WhatsApp cases should never expose raw message bodies, phone numbers, customer names, addresses, or sensitive support text.

4. **No implied side effects**
   - Suggested actions must be phrased as suggestions/manual/approval-required unless a governed execution path exists.
   - Test that copy does not say Orvo replied, paused, refunded, or executed anything.

5. **Separate dispatch idempotency/ledger outcome**
   - Successful case projection and dispatch ledger should remain separate.
   - Secondary dispatch failures should not leave runs `running`; they should be recorded as terminal/partial with redacted failure summaries.

6. **Golden owner brief**
   - Add Spanish golden fixtures for healthy, degraded, and stale-data briefs.
   - Assert stale/missing data is explicitly called out.

## Gap 5 — internal operator API surface consistency

### Current coverage

The internal API has stable envelopes, business scoping, route auth invariants, and redaction checks. Case action idempotency is covered.

### Missing coverage

The readiness/dry-run/force-dispatch parts of the API contract are not represented in the inspected tests.

### Actionable tests to add

1. **Endpoint inventory contract**
   - Assert documented initial endpoints either exist or are explicitly disabled with safe envelopes.
   - Do not let docs drift ahead of implementation.

2. **Business scope test for run detail**
   - Run detail should deny cross-business access.
   - Existing tests touch run detail; add explicit negative test for another business ID.

3. **Admin-only audit export test**
   - Viewer/operator roles should receive safe `403`.
   - Admin export should respect `retention_days` limits and redaction.

4. **Redaction on error paths**
   - Failed compile/readiness/dry-run responses should include `redaction_applied=true` and no raw secret-shaped headers/tokens.

## Recommended next worker packets

Keep these small and test-first:

1. **Packet A: operator API endpoint inventory**
   - Add tests that compare documented internal operator endpoints against registered routes.
   - Mark missing endpoints as expected gaps if implementation is intentionally deferred.

2. **Packet B: OS snapshot projection**
   - Add a service-level OS snapshot model over connector/runtime/case state.
   - Keep routes thin.
   - Add golden tests for healthy/degraded/stale businesses.

3. **Packet C: readiness-gated setup cases**
   - Add deterministic `data_stale`/setup-required case tests for missing/stale connectors.
   - Prove suppression of dependent owner-facing claims.

4. **Packet D: WhatsApp owner-brief invariants**
   - Add golden Spanish brief tests.
   - Prove actionable-only, no resolved cases, truthful truncation counts, no raw PII, no implied side effects.

5. **Packet E: case recurrence and priority invariants**
   - Add tests for resolved recurrence, deterministic ordering, and evidence freshness.

## QA verdict

The current operator console work is a solid internal case/run inspection layer, but it is not yet a complete app-first PyME OS snapshot. The highest-value next QA work is not more generic dashboard coverage; it is **readiness-gated module state plus owner-brief invariants**.

The repo should not present the first product as a chatbot, dashboard-only analytics tool, or WhatsApp control panel. The safest MVP path is:

1. Tiendanube sales/orders as the trusted automated core;
2. module readiness lanes for stock/fulfillment, customer attention, ARCA/fiscal, and treasury/reporting;
3. setup-required or `data_stale` cases where evidence is missing/stale;
4. operator console as the canonical control surface;
5. WhatsApp as concise, evidence-backed alerts only.

## Verification performed

- Inspected operator-surface/product/runtime/registry/case/API/testing docs.
- Inspected operator dashboard, case view, internal API, route auth, case action, and run projection tests.
- Confirmed no production code was modified in this task.
- No secrets were read, copied, or written into this document.

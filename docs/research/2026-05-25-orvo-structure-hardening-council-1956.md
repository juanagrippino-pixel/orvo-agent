# Orvo Structure / Organization / Hardening Council — 2026-05-25 19:56

Status: durable research synthesis
Branch: `research/orvo-structure-hardening-20260525-1956`
Scope: structure, organization, hardening, pilot readiness, and architecture refinement only
Strategy constraint: no broad new end-user product functions

## Council inputs

This synthesis combines four read-only specialist passes:

1. architecture / bounded-context structure;
2. autonomous-worker organization and release train hygiene;
3. hardening, tests, redaction, idempotency, and run-ledger completeness;
4. ARTEMEA/Hito0 pilot packaging, readiness, trust, and observability.

The council inspected the current repo state and recent docs/code around runtime compilation, connector registry, run ledger, Operational Cases, evidence snapshots, internal operator API/JQL-lite views, reporting, dispatch, and Tiendanube/WhatsApp pilot readiness.

## Strategy constraint

Do **not** add broad new end-user product functions in the next train. Orvo already has enough current wedge surface:

- D2C ecommerce operations control plane;
- deterministic reports;
- Operational Cases;
- evidence snapshots;
- internal operator API / JQL-lite views;
- WhatsApp owner briefs as a projection/delivery surface.

Expansion now means making those surfaces safer, more coherent, faster to certify, easier to sell honestly, and easier for autonomous workers to extend without bypassing the platform contracts.

## Current risk

### 1. Release docs lag shipped owner-brief behavior

`docs/specs/integration-train-contract.md` still frames case-backed owner/operator briefs as a dry projection step, but current code can dispatch owner case briefs from scheduled/forced flows through:

- `app/brain/runner.py`;
- `scripts/run_orvo_brain_reports.py`;
- `app/brain/execution_ledger.py`;
- `app/brain/dispatch.py`.

Tests now expect both a daily report dispatch and an `owner_case_brief` dispatch in due-report flows. This may be the right eventual behavior, but it is currently governed by implementation reachability rather than an explicit release decision.

**Risk:** a worker or operator may treat owner case briefs as live-certified even though the docs still require dry projection, claim allowlists, and pilot gates.

### 2. Current-vs-target module ownership is ambiguous

The implementation is still mostly flat and compatibility-oriented:

- `app/brain/runtime.py`;
- `app/brain/connector_registry.py`;
- `app/brain/run_ledger.py`;
- `app/brain/execution_ledger.py`;
- `app/brain/operational_cases.py`;
- `app/brain/operator_api.py`;
- `app/brain/operator_views.py`;
- `app/brain/reporting.py`;
- `server.py`;
- `scripts/run_orvo_brain_reports.py`.

Several docs/worker packets still mention target paths such as `app/brain/runtime/compiled.py`, `app/brain/connectors/registry.py`, and `app/brain/cases/engine.py`.

**Risk:** autonomous workers may create duplicate package structures or reimplement service logic instead of hardening the current source of truth.

### 3. `execution_ledger.py` has become a post-run god object

`app/brain/execution_ledger.py` currently spans multiple bounded contexts:

- run ledger start/end;
- connector outcome recording;
- artifact refs;
- Operational Case mutation;
- owner case brief construction/dispatch;
- dispatch outcome recording;
- failure finalization;
- `data_stale` case creation on failures.

This is acceptable as a transitional shim, but it is too coupled to remain the architecture center.

**Risk:** future fixes to dispatch, cases, or ledger behavior will collide in one central file and accidentally change side effects.

### 4. Case identity still depends on rendered text

`app/brain/operational_cases.py` still maps some case types from insight-title substrings such as stock/ventas/conversaciones/channel words. That makes workflow identity sensitive to copy edits.

**Risk:** a harmless Spanish wording change can silently change case family, dedupe, or owner-facing workflow behavior.

### 5. Public preview/report error redaction remains weaker than internal API redaction

Internal operator API paths use safer error envelopes, but public report/preview routes in `server.py` still return raw `str(e)` in multiple connector error paths.

**Risk:** adapter/client exceptions containing token-shaped strings, OAuth codes, signed URLs, or auth headers can be reflected in JSON responses.

### 6. Failed-run provenance is still incomplete in ambiguous cases

Exact connector failures are improving, but ambiguous multi-connector or pre-dispatch failures can still end in a terminal failed run without enough inspectable connector provenance, while stale-data case creation may over-attribute affected connectors.

**Risk:** an operator cannot always answer what failed, which connectors were implicated, and whether downstream claims were suppressed safely.

### 7. Golden/eval coverage is not certification-grade yet

Projection tests exist, but there is still no dedicated `tests/golden/` and `tests/fixtures/golden/` suite for reports, owner briefs, degraded/stale states, truncation, unsupported claims, and redaction.

**Risk:** substring tests can pass while owner-facing copy loses evidence, caveats, source attribution, or safe truncation behavior.

### 8. Pilot readiness remains internal rehearsal, not live paid-pilot green

The council found/confirmed a repo-local ignored `orvo_brain.sqlite3` exists. A readiness specialist inspected metadata/schema/counts without printing secret values and reported an ARTEMEA `business_configs` row with enabled Tiendanube and Meta Ads connectors containing `access_token` parameter keys.

**Risk:** repo-local operational DB state, possible real tokens, and Meta Ads scope drift are no-go conditions for a Tiendanube/WhatsApp-first live paid pilot.

### 9. Operational Case and operator API contracts imply more than v0 implements

Current case lifecycle is narrower than target docs:

- implemented v0: `open`, `acknowledged`, `resolved`, comments/actions around acknowledge/resolve/comment;
- target/future: `in_progress`, `dismissed`, richer assignment/follow-up/external-action semantics.

Current internal routes cover cases/views/actions/runs, while target contracts also describe compile-preview/readiness/dry-run/force-dispatch surfaces.

**Risk:** workers may assume future target endpoints/statuses are already landed and build on false premises.

## Structural recommendation

### A. Make the next train a certification/reconciliation train

Do not add product breadth. The next train should classify every existing surface as one of:

- `landed`;
- `landed-needs-certification`;
- `blocked`;
- `superseded`;
- `next`;
- `parked/non-goal`.

The train must explicitly distinguish:

- implemented;
- certified by tests/invariants;
- pilot-ready;
- owner-facing-enabled.

### B. Add an explicit owner-brief delivery decision

Owner case briefs should be recorded in docs and code as exactly one of:

1. `dry_only`;
2. `explicit_flag_gated`;
3. `pilot_approved_live`.

Recommendation: default to **explicit flag-gated** (or dry-only if implementation work is not yet scheduled). Do not let the existence of a dispatch path imply live pilot approval.

### C. Publish a current-vs-target bounded-context ownership map

Create one canonical table that maps current flat modules to bounded contexts, target extraction paths, allowed dependents, migration blockers, and required tests. Target nested packages should be labelled as future extraction paths until a migration packet explicitly owns them.

Suggested context map:

| Context | Current source of truth | Target extraction path | Immediate rule |
|---|---|---|---|
| Runtime & orchestration | `runtime.py`, `runner.py`, `pipeline.py`, `scripts/run_orvo_brain_reports.py`, parts of `execution_ledger.py` | `app/brain/runtime/*` | current flat modules are authoritative |
| Connectors & ingestion | `connector_registry.py`, `adapters/*`, connector branches in `pipeline.py` | `app/brain/connectors/*` | registry wrappers before rewrites |
| Semantics & insights | `models.py`, `insights.py`, `semantics/metric_registry.py` | `app/brain/semantics/*` | metric registry is the semantic source |
| Cases & workflow | `operational_cases.py` | `app/brain/cases/*` | v0 lifecycle only until docs/tests say otherwise |
| Projections & delivery | `reporting.py`, `dispatch.py`, `operator_api.py`, `operator_views.py`, `server.py` | `app/brain/projections/*`, `app/brain/operator_api/*` | projections are not source of truth |
| Trust / audit / observability | `security/redaction.py`, `run_ledger.py`, `storage.py` | `app/brain/security/*`, `app/brain/audit/*` | redaction and ledger invariants first |

### D. Split post-run side effects into named services without a broad package migration

Do not start a full nested-package migration. First introduce/extract service seams around existing flat files:

```text
RuntimeExecutionService
  -> RunLedgerRecorder
  -> CaseMutationService
  -> ProjectionBuilder
  -> DispatchPolicy / DispatchOutbox
```

The immediate architectural goal is to make side effects explicit and testable, not to rearrange directories.

### E. Introduce a deterministic `CaseCandidate` seam

Case identity should flow from deterministic metric/evidence/case-family rules:

```text
metric/evidence inputs
  -> deterministic detection rule
  -> CaseCandidate(case_family, entity_scope, metric_refs, dedupe_parts, severity, evidence_refs)
  -> Operational Case upsert/update
  -> report / owner brief projection
```

`Insight` and report copy can remain for owner/operator wording, but must not determine workflow identity.

### F. Treat ARTEMEA/Hito0 as internal rehearsal until readiness gates pass

Current state should be messaged internally as:

- **Live paid pilot:** no-go;
- **Internal rehearsal/backtest:** yes, under constraints;
- **External dispatch:** disabled, dry-only, or explicitly gated until approval.

Required preconditions before paid pilot:

- local operational DB sanitized/moved and tokens rotated if real;
- ARTEMEA pilot config narrowed to Tiendanube-only unless Meta Ads is separately certified;
- owner brief dispatch state documented and enforced;
- SKU/product-level stockout evidence/dedupe certified before stockout claims;
- public HTTP errors redacted;
- failed-run provenance complete;
- golden owner/operator projection fixtures pass.

## Exact repo artifacts to update

### Create

- `docs/organization/2026-05-25-control-plane-certification-train.md`
  - packet/surface disposition;
  - implemented vs certified vs pilot-ready vs owner-facing-enabled matrix;
  - owner case brief delivery state.
- `docs/organization/integration-queue.md`
  - single release queue with packet, branch, worktree, SHA, files, tests, review state, conflicts, merge order, promotion decision.
- `docs/organization/decision-log.md`
  - owner brief delivery state;
  - current-vs-target module policy;
  - pilot readiness state;
  - certification-train scope freeze.
- `docs/architecture/bounded-context-ownership-map.md`
  - current module -> bounded context -> target path -> owner lane -> allowed dependents -> migration blocker -> tests.
- Later code/QA packet: `tests/golden/test_brain_reporting_golden.py`.
- Later code/QA packet: `tests/fixtures/golden/`.

### Modify

- `docs/specs/integration-train-contract.md`
  - reconcile dry-projection wording with current owner-brief dispatch code;
  - add owner-facing promotion gate.
- `docs/organization/d2c-worker-task-packets.md`
  - add current dispositions for Packets A-M;
  - mark future package paths as future extraction unless explicitly migrated;
  - add certification/hardening packets before feature work.
- `docs/organization/d2c-autonomous-worker-addendum.md`
  - add certify-existing-surfaces-first rule;
  - add central-file sequencing rule.
- `docs/specs/worker-handoff-manifest.md`
  - add packet/lane/dependency/release-decision/gates fields.
- `docs/architecture/phase-a-control-plane-contract.md`
  - add current-vs-target path warning;
  - name service seams around post-run side effects.
- `docs/adr/0001-control-plane-bounded-contexts-and-module-ownership.md`
  - align current flat modules with target contexts.
- `docs/specs/compiled-runtime-contract.md`
  - document that compiled runtime exists but execution is still partially branch-based;
  - define next `RuntimeExecutionService` seam.
- `docs/specs/connector-registry-contract.md`
  - clarify registry execution wrappers should become the dispatch source before connector expansion.
- `docs/specs/run-ledger-foundation.md`
  - add ambiguous/pre-dispatch failure provenance requirement.
- `docs/specs/operational-case-engine-contract.md`
  - distinguish implemented v0 lifecycle from target lifecycle;
  - add `CaseCandidate` requirement.
- `docs/specs/internal-operator-api-contract.md`
  - distinguish implemented v0 routes from target routes.
- `docs/specs/d2c-operator-surface-contract.md`
  - align current actions/statuses with v0 implementation.
- `docs/specs/tenant-secret-redaction-contract.md`
  - add public HTTP error response redaction and repo-local artifact-at-rest guidance.
- `docs/specs/testing-invariant-matrix.md`
  - add public error redaction, ambiguous failure provenance, golden projection, idempotency, owner-claim allowlist checks.
- `docs/ops/d2c-pilot-readiness-checklist.md`
  - top-level current state = internal rehearsal only;
  - hard no-go for repo-local secret-bearing DB/artifacts;
  - owner brief live-send gate;
  - Meta Ads disabled for Tiendanube-only pilot unless separately certified.
- `docs/ops/d2c-pilot-runbook.md`
  - ARTEMEA preflight and incident response for local DB/token exposure.
- `docs/orvo-brain-runtime.md`
  - document transitional inline-token compatibility vs pilot secret-ref expectation;
  - document owner brief dispatch gate.
- `docs/gtm/2026-05-25-orvo-first-paid-product-pricing-packaging.md`
  - keep paid-pilot packaging conditional on readiness gates.
- `docs/product/tiendanube-exception-desk-opportunity-spec.md`
  - align claims with v0 lifecycle and current certified surfaces.

## Implementation packets

### Packet CR-1 — Certification train and owner-brief decision docs

**Goal:** make current surface state and owner-facing delivery policy impossible to misunderstand.

**Files:**

- Create: `docs/organization/2026-05-25-control-plane-certification-train.md`
- Create: `docs/organization/integration-queue.md`
- Create: `docs/organization/decision-log.md`
- Modify: `docs/specs/integration-train-contract.md`
- Modify: `docs/organization/d2c-worker-task-packets.md`
- Modify: `docs/ops/d2c-pilot-readiness-checklist.md`

**Acceptance gates:**

- Packets/surfaces have disposition: landed, landed-needs-certification, blocked, superseded, next, parked.
- Owner case brief delivery state is documented as dry-only, flag-gated, or approved.
- Implemented/certified/pilot-ready/owner-facing-enabled are separate columns.
- No code changes.
- Docs hygiene checks pass.

### Packet CR-2 — Bounded-context ownership map docs

**Goal:** prevent duplicate package/service implementations.

**Files:**

- Create: `docs/architecture/bounded-context-ownership-map.md`
- Modify: `docs/adr/0001-control-plane-bounded-contexts-and-module-ownership.md`
- Modify: `docs/architecture/phase-a-control-plane-contract.md`
- Modify: `docs/organization/d2c-worker-task-packets.md`

**Acceptance gates:**

- Every current flat module maps to exactly one bounded context.
- Target package paths are marked future unless a packet explicitly owns migration.
- Central files have sequencing/ownership notes.
- No code changes.

### Packet CR-3 — Public HTTP error redaction invariant

**Goal:** public report/preview endpoints never echo raw secret-shaped exception strings.

**Files:**

- `server.py`
- `tests/test_server_brain_tiendanube.py`
- `tests/test_server_brain_mercadolibre.py`
- `tests/test_server_brain_meta_ads.py`
- `tests/test_server_brain_csv.py`
- optionally Google Sheets endpoint tests
- `tests/invariants/test_secret_redaction.py`

**Acceptance gates:**

- Shared helper redacts public error responses before serialization.
- Fake adapter errors containing bearer tokens, access-token query params, refresh-token strings, OAuth codes, and Basic auth shapes are redacted.
- Success response shapes stay backward-compatible.
- Focused endpoint tests and `pytest -q` pass.

### Packet CR-4 — Failed-run provenance and data-stale attribution

**Goal:** every failed run has inspectable, safe provenance without false connector blame.

**Files:**

- `app/brain/execution_ledger.py`
- `app/brain/run_ledger.py`
- `tests/test_brain_runner.py`
- `tests/test_run_orvo_brain_reports_script.py`
- `tests/test_brain_run_ledger.py`
- `docs/specs/run-ledger-foundation.md`

**Acceptance gates:**

- Exact connector failures remain exact.
- Ambiguous multi-connector/pre-dispatch failures record explicit `ambiguous` or `runtime` provenance.
- Failed run cannot be terminal with zero provenance unless a controlled runtime-level outcome exists.
- `data_stale` cases do not falsely blame every connector unless policy says all dependent data is stale.
- Failure summaries are redacted.

### Packet CR-5 — Deterministic CaseCandidate seam

**Goal:** stop deriving workflow identity from rendered insight/report copy.

**Files:**

- `app/brain/operational_cases.py`
- `app/brain/insights.py`
- `app/brain/semantics/metric_registry.py`
- `tests/test_brain_operational_cases.py`
- `tests/test_brain_insights.py`
- `docs/specs/operational-case-engine-contract.md`
- `docs/specs/d2c-case-family-catalog.md`

**Acceptance gates:**

- A deterministic case-candidate representation is keyed by registered family/metric/evidence/entity scope.
- Changing insight title/explanation/recommended-action copy does not change case family or dedupe identity.
- Current owner-facing wording remains compatible.
- No new case families.

### Packet CR-6 — Owner brief dispatch policy and idempotency certification

**Goal:** prevent accidental second live WhatsApp/case brief delivery while preserving audited dispatch records.

**Files:**

- `app/brain/dispatch.py`
- `app/brain/runner.py`
- `scripts/run_orvo_brain_reports.py`
- `app/brain/execution_ledger.py`
- `tests/test_brain_dispatch.py`
- `tests/test_brain_runner.py`
- `tests/test_run_orvo_brain_reports_script.py`
- `docs/specs/integration-train-contract.md`
- `docs/ops/d2c-pilot-readiness-checklist.md`

**Acceptance gates:**

- Owner case brief is disabled/dry-only by default or requires explicit policy/flag.
- Live owner case brief dispatch requires an explicit decision/config.
- Daily report dispatch remains backward-compatible.
- Daily and owner brief idempotency keys remain separate.
- Skipped-by-policy, sent, duplicate-skipped, and failed secondary dispatch are recorded safely.

### Packet CR-7 — Golden owner/operator projection evals

**Goal:** certify existing projections before pilot.

**Files:**

- Create: `tests/golden/test_brain_reporting_golden.py`
- Create: `tests/fixtures/golden/`
- Modify only if tests expose bugs: `app/brain/reporting.py`, `app/brain/operator_api.py`
- Modify: `docs/specs/testing-invariant-matrix.md`

**Acceptance gates:**

- Fixtures cover healthy, degraded, stale/unauthorized, truncated queue, sales-drop, stockout-risk, and no-open-cases paths.
- Tests normalize volatile IDs/timestamps only.
- Evidence/source/caveat text is preserved.
- Raw secret-shaped strings are absent.
- Unsupported metrics/actions/case families are absent.
- No live API calls.

### Packet CR-8 — ARTEMEA pilot runbook and local-state sanitation

**Goal:** make internal rehearsal safe and make live-pilot no-go conditions explicit.

**Files:**

- `docs/ops/d2c-pilot-readiness-checklist.md`
- `docs/ops/d2c-pilot-runbook.md`
- `docs/orvo-brain-runtime.md`
- `docs/gtm/2026-05-25-orvo-first-paid-product-pricing-packaging.md`
- `docs/product/tiendanube-exception-desk-opportunity-spec.md`

**Operational actions:**

- Do not commit DB state.
- Sanitize or move repo-local `orvo_brain.sqlite3` before live pilot use.
- Rotate Tiendanube/Meta tokens if any local values are real.
- Disable Meta Ads in ARTEMEA Tiendanube-only pilot config unless separately certified.

**Acceptance gates:**

- Docs say current state is internal rehearsal only until gates pass.
- No new product promise is added.
- Live paid-pilot packaging is conditional on readiness gates.
- Runbook includes preflight, dry-run, ledger/case/evidence inspection, dispatch decision, and incident response.

## Non-goals / deferred work

Explicitly defer:

- new first-pilot connectors;
- Meta Ads / MercadoLibre / channel-mix owner-facing expansion;
- fulfillment backlog owner-facing claims until Tiendanube field truth gates pass;
- WhatsApp inbox ingestion;
- unanswered-conversation owner-facing cases;
- marketplace/developer platform work;
- generic chatbot or generic agent-platform positioning;
- saved custom views or dashboard expansion;
- public customer API expansion;
- autonomous external actions on ads, stock, orders, refunds, prices, or customer messages;
- broad workflow automation beyond audited case actions;
- full package migration from flat modules to nested packages;
- Hito0/report polish that bypasses runtime, registry, ledger, cases, evidence, or audit contracts.

Feature ideas discovered during this council should be recorded as parking-lot/non-goals unless they directly harden existing D2C control-plane behavior.

## Guardrails

- Keep `/root/orvo-agent` clean; autonomous writes only in external worktrees.
- Do not create, update, remove, or schedule cron jobs from this lane.
- Do not push or deploy.
- Treat WhatsApp as projection/delivery only, never source of truth.
- Do not let report text, owner-brief copy, or LLM/copy layers create metrics, cases, priorities, lifecycle transitions, or actions.
- Every owner-facing number must trace to deterministic evidence.
- Redact at every boundary: runtime, ledger, cases, artifacts, public errors, internal API, docs/examples, golden fixtures, and local operational state.
- Preserve current Hito0/daily-report compatibility while hardening the control plane.
- Keep current flat modules authoritative until a docs-approved extraction packet lands.
- Require focused tests, full `pytest -q`, spec review, and quality/safety review before merging code packets.
- Owner-facing dispatch requires an explicit decision-log entry and release gate before live pilot use.
- Local SQLite/config secrets are a live-pilot no-go until sanitized/moved and rotated if real.

## Next implementation packet

Start with **Packet CR-1 — Certification train and owner-brief decision docs**.

Reason: it resolves the highest governance risk without code churn. It tells every future worker which current surfaces are landed, which are certified, which are pilot-ready, and whether owner case brief dispatch is dry-only, flag-gated, or live-approved. After CR-1, run CR-2 to prevent duplicate module/service work, then CR-3 and CR-4 for boundary hardening before any owner-facing promotion.

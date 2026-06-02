# Orvo Structure / Organization / Hardening Council — 2026-05-25 15:16

Status: durable research synthesis  
Branch: `research/orvo-structure-hardening-20260525-1516`  
Scope: structure, organization, hardening, pilot readiness, and architecture refinement only

## Strategy constraint

Do **not** add broad new end-user product functions in the next train. Orvo already has enough product surface for the current wedge:

- D2C ecommerce operations control plane;
- deterministic reports;
- Operational Cases;
- evidence snapshots;
- internal operator API / JQL-lite views;
- WhatsApp owner briefs as a projection/delivery surface.

Expansion now means making those surfaces safer, more coherent, faster to finish, easier to review, and easier for autonomous workers to extend without bypassing the platform contracts.

## Current risk

### 1. Structural convergence debt

The docs describe bounded contexts and future package paths, but current implementation is still concentrated in flat compatibility modules:

- `app/brain/runtime.py`
- `app/brain/connector_registry.py`
- `app/brain/execution_ledger.py`
- `app/brain/operational_cases.py`
- `app/brain/operator_api.py`
- `app/brain/operator_views.py`
- `server.py`
- `scripts/run_orvo_brain_reports.py`

This is acceptable for the current branch, but worker packets still reference target paths like `app/brain/runtime/compiled.py` and `app/brain/cases/engine.py`. That mismatch can cause autonomous workers to invent conflicting package layouts or duplicate service logic.

### 2. Release train outran certification docs

`docs/specs/integration-train-contract.md` still describes case-backed owner/operator briefs as a dry projection before WhatsApp delivery changes, while current code has landed owner case brief dispatch paths. The next train should reconcile what is implemented, what is certified, what is pilot-ready, and what is owner-facing-enabled.

### 3. Owner-facing delivery gate is not explicit enough

A successful run can send the legacy daily report and may also send a case brief. That may be useful later, but it needs a release decision, claim allowlist, and pilot gate before being treated as safe live behavior. WhatsApp must remain a projection/delivery surface, not the source of truth.

### 4. Contract/code drift in Operational Cases

The Operational Case contract includes richer statuses/actions than the current implementation. Current code supports a narrower v0 lifecycle around open/acknowledged/resolved and operator comments/actions. This can be fine, but it must be called out as v0 rather than letting reviewers assume `in_progress`/`dismissed` already exist.

### 5. Hardening gaps remain at boundaries

Positive controls already exist: compiled runtime redaction, connector registry tests, metric registry tests, run ledger tests, Operational Case evidence tests, operator API scoping/redaction, and secret redaction invariants.

Remaining boundary risks:

- public report API error responses can still reflect raw `str(e)` unless every route redacts exception messages;
- ambiguous multi-connector/pre-dispatch failures can leave run ledger connector provenance incomplete;
- golden output/eval coverage is mostly substring-based instead of fixture-based;
- compiled runtime secret refs are safe strings but less provenance-rich than the documented `SecretRef` contract.

### 6. Pilot readiness is red/yellow, not green

A read-only audit confirmed an untracked local `orvo_brain.sqlite3` exists in the repo root and contains secret-shaped fields in `business_configs`. Values were not inspected or reproduced here. This is an operational no-go until sanitized/rotated outside this docs-only run.

A council member also found the local ARTEMEA state is not ready for live paid operation: current readiness should be internal dry-run/backtest only until Tiendanube readiness, redaction-at-rest, stale-data handling, and owner-brief gates pass.

## Structural recommendation

### A. Publish a current-vs-target bounded-context map

Before assigning more implementation workers, add a docs-first ownership map that distinguishes:

- current implementation file;
- target package/module path;
- bounded context owner;
- allowed dependents;
- migration blocker;
- contract tests required before dependents can rely on the seam.

This avoids a package migration disguised as a small task and prevents duplicate orchestration code.

### B. Turn the next train into certification/reconciliation, not feature expansion

The next train should classify existing packets and recent shipped code as:

- landed;
- landed but needs certification;
- blocked;
- superseded;
- next;
- parked/non-goal.

The release train must explicitly say whether owner case brief dispatch is dry-only, flag-gated, or approved for live pilot use.

### C. Split post-run side effects into named services/policies

Current post-run behavior should converge toward:

```text
runtime execution
  -> run ledger recorder
  -> case mutation service
  -> projection builder
  -> dispatch policy / outbox
```

`execution_ledger.py` should not be the implicit place where ledger writes, case mutation, case projection, and WhatsApp dispatch policy blend together.

### D. Stop deriving workflow identity from report/insight text

Case creation should be based on deterministic metric/evidence/case-family rules, not title substrings. Report and WhatsApp text are projections; they must not become workflow source of truth.

### E. Add certification-grade golden/eval artifacts

Move beyond substring assertions for owner/operator text. Add deterministic golden fixtures for healthy, degraded, stale, truncated, and case-family-specific projections. Golden checks should assert evidence freshness/caveats and absence of raw secret-shaped values.

## Exact repo artifacts to update

### Architecture / structure

- `docs/architecture/phase-a-control-plane-contract.md`
- `docs/adr/0001-control-plane-bounded-contexts-and-module-ownership.md`
- New: `docs/architecture/bounded-context-ownership-map.md`
- `docs/specs/compiled-runtime-contract.md`
- `docs/specs/connector-registry-contract.md`
- `docs/specs/run-ledger-foundation.md`
- `docs/specs/operational-case-engine-contract.md`
- `docs/specs/internal-operator-api-contract.md`

### Organization / release train

- `docs/specs/integration-train-contract.md`
- `docs/organization/d2c-worker-task-packets.md`
- `docs/organization/d2c-autonomous-worker-addendum.md`
- `docs/specs/worker-handoff-manifest.md`
- New: `docs/organization/2026-05-25-control-plane-certification-train.md`
- New: `docs/organization/integration-queue.md`
- New: `docs/organization/decision-log.md`

### Hardening / QA

- `docs/specs/testing-invariant-matrix.md`
- `docs/specs/tenant-secret-redaction-contract.md`
- `tests/invariants/test_secret_redaction.py`
- `tests/contracts/test_compiled_runtime_contract.py`
- `tests/contracts/test_connector_registry_contract.py`
- `tests/contracts/test_metric_validation_contract.py`
- `tests/test_brain_run_ledger.py`
- `tests/test_brain_operational_cases.py`
- `tests/test_brain_reporting.py`
- `tests/test_internal_operator_api.py`
- New: `tests/golden/test_brain_reporting_golden.py`
- New: `tests/fixtures/golden/`

### Operations / packaging readiness

- `docs/ops/d2c-pilot-readiness-checklist.md`
- `docs/ops/d2c-pilot-runbook.md`
- `docs/product/d2c-control-plane-prd.md`
- `docs/product/tiendanube-exception-desk-opportunity-spec.md`
- `docs/gtm/2026-05-25-orvo-first-paid-product-pricing-packaging.md`
- `examples/tiendanube_business_config.json`
- `examples/meta_ads_business_config.json`

## Implementation packets

### Packet SH-1 — Bounded-context ownership map refresh

**Goal:** make current-vs-target module ownership explicit before more workers touch central files.

**Files:**

- Create: `docs/architecture/bounded-context-ownership-map.md`
- Modify: `docs/adr/0001-control-plane-bounded-contexts-and-module-ownership.md`
- Modify: `docs/architecture/phase-a-control-plane-contract.md`
- Modify: `docs/organization/d2c-worker-task-packets.md`

**Acceptance gates:**

- Every current flat module maps to one bounded context.
- Target package paths are marked as future migrations, not current worker targets.
- Worker packets stop referencing impossible package paths without a migration note.
- Docs-only checks pass: `git diff --check`, markdown link scan if available, and secret scan.

### Packet SH-2 — Release-train reconciliation and owner-brief decision

**Goal:** make the current control-plane train certifiable and prevent accidental duplicate/live owner delivery.

**Files:**

- Modify: `docs/specs/integration-train-contract.md`
- Modify: `docs/organization/d2c-worker-task-packets.md`
- Create: `docs/organization/2026-05-25-control-plane-certification-train.md`
- Create: `docs/organization/integration-queue.md`
- Create: `docs/organization/decision-log.md`
- Modify: `docs/ops/d2c-pilot-readiness-checklist.md`

**Acceptance gates:**

- Packets A–M have disposition: landed, certification-needed, blocked, superseded, next, or parked.
- Owner case brief delivery has a documented state: dry-only, explicit flag-gated, or approved.
- Release docs distinguish implemented, certified, pilot-ready, and owner-facing-enabled.
- No code changes in this packet.

### Packet SH-3 — HTTP error redaction invariant

**Goal:** ensure public report endpoints cannot reflect raw credentials in JSON error responses.

**Likely files:**

- `server.py`
- `tests/test_server_brain_tiendanube.py`
- `tests/test_server_brain_mercadolibre.py`
- `tests/test_server_brain_meta_ads.py`
- optionally `tests/test_server_brain_csv.py`
- optionally `tests/test_server_brain_google_sheets.py`

**Acceptance gates:**

- Shared server helper redacts exception messages before response serialization.
- Fake adapter exceptions containing token-shaped strings are redacted in every affected endpoint.
- Success payload shapes remain backward-compatible.
- Focused endpoint tests and `pytest -q` pass.

### Packet SH-4 — Failed run ledger completeness

**Goal:** every failed run has inspectable connector provenance, even when attribution is ambiguous.

**Likely files:**

- `app/brain/execution_ledger.py`
- `tests/test_brain_runner.py`
- `docs/specs/run-ledger-foundation.md`

**Acceptance gates:**

- Exact connector failures remain exact.
- Ambiguous pre-dispatch/multi-connector failures record explicit ambiguous provenance or a documented controlled alternative.
- Failed runs redact exception text and do not falsely blame a specific connector.
- Focused runner/ledger tests and `pytest -q` pass.

### Packet SH-5 — Case candidate contract

**Goal:** stop deriving Operational Case identity from rendered insight/report titles.

**Likely files:**

- `app/brain/operational_cases.py`
- `app/brain/insights.py`
- `app/brain/semantics/metric_registry.py`
- `tests/test_brain_operational_cases.py`
- `tests/test_brain_insights.py`
- `docs/specs/operational-case-engine-contract.md`
- `docs/specs/d2c-case-family-catalog.md`

**Acceptance gates:**

- Introduce a deterministic case-candidate seam keyed by registered case family.
- Preserve current owner-facing wording.
- Tests prove changing insight title text does not change case family identity.
- No new case families are added.

### Packet SH-6 — Golden output and evidence evals

**Goal:** catch projection/wording/evidence regressions before pilot.

**Likely files:**

- Create: `tests/golden/test_brain_reporting_golden.py`
- Create: `tests/fixtures/golden/`
- Modify if needed: `app/brain/reporting.py`
- Modify if needed: `app/brain/operator_api.py`
- Modify: `docs/specs/testing-invariant-matrix.md`

**Acceptance gates:**

- Golden fixtures cover healthy, degraded, stale, truncated, sales-drop, and stockout-risk projections.
- Golden assertions normalize dates/IDs but preserve evidence/source/caveat text.
- Tests assert no raw secret-shaped values and no unsupported metrics/actions.
- No live API calls.

### Packet SH-7 — Pilot ops/admin readiness hardening

**Goal:** make concierge pilot operation repeatable without overstating readiness.

**Files:**

- `docs/ops/d2c-pilot-readiness-checklist.md`
- `docs/ops/d2c-pilot-runbook.md`
- `docs/gtm/2026-05-25-orvo-first-paid-product-pricing-packaging.md`
- `docs/product/tiendanube-exception-desk-opportunity-spec.md`

**Acceptance gates:**

- Checklist says current state is internal rehearsal until gates pass.
- Raw SQLite/config secrets are a hard no-go and token rotation/sanitization is documented.
- Tiendanube readiness distinguishes unauthorized, 404/not found, rate-limited, malformed, stale, degraded, and ok.
- Meta Ads, MercadoLibre, channel mix, fulfillment backlog, and unanswered conversations remain parked/internal unless separately certified.

## Non-goals / deferred work

Explicitly defer:

- new connectors as first-pilot dependencies;
- marketplace/developer platform work;
- generic chatbot or generic agent-platform positioning;
- saved custom views or dashboard expansion;
- public API expansion;
- autonomous external actions;
- broad workflow automation beyond dry-run/internal approval gates;
- Meta Ads / MercadoLibre / channel-mix owner-facing claims;
- owner-facing fulfillment backlog until Tiendanube field truth gates pass;
- WhatsApp inbox ingestion or unanswered-conversation cases;
- full package migration from flat modules to nested packages unless separately planned.

Parking-lot ideas should be recorded as non-goals unless they directly harden current D2C control-plane behavior.

## Guardrails

- Keep `/root/orvo-agent` clean; autonomous edits only in external worktrees.
- Do not create/update/remove/schedule cron jobs from this lane.
- Do not push or deploy.
- Do not let WhatsApp reports, briefs, or copy become workflow source of truth.
- Do not let LLM/copy layers create metrics, cases, priorities, lifecycle transitions, or actions.
- Keep all business calculations deterministic and evidence-backed.
- Redact at every boundary: runtime, ledger, case snapshots, API responses, errors, docs/examples, and golden fixtures.
- Preserve Hito0/report compatibility while hardening the control plane.
- Require focused tests, full `pytest -q`, spec review, and quality/safety review before merging code packets.
- Treat docs-only branches as real deliverables: inspect, run hygiene checks, commit, and keep parent clean.

## Next implementation packet

Start with **Packet SH-2 — Release-train reconciliation and owner-brief decision**.

Reason: it reduces the highest governance risk without code churn. It will tell future workers exactly which landed surfaces need certification, whether owner case brief delivery is dry-only or flag-gated, and which packets are parked. After SH-2, dispatch SH-1 if workers are still confused by current-vs-target file paths; then SH-3/SH-4 for boundary hardening.

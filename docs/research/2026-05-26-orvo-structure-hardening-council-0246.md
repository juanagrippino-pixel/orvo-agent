# Orvo Structure / Organization / Hardening Council — 2026-05-26 02:46

Status: durable research synthesis
Branch: `research/orvo-structure-hardening-20260526-0246`
Scope: structure, organization, hardening, pilot readiness, and architecture refinement only
Strategy constraint: no broad new end-user product functions

## Council inputs

This synthesis combines four read-only specialist passes:

1. architecture / bounded-context structure;
2. autonomous-worker organization and release-train hygiene;
3. QA, invariants, redaction, idempotency, and run-ledger completeness;
4. ARTEMEA/Hito0 and Tiendanube pilot packaging/readiness.

The council inspected the current repo state on `feat/configurable-insight-thresholds` at `f147627` (`feat: ingest Meta WhatsApp delivery statuses`) plus the recent Meta Cloud dispatch and owner-brief age/status commits. No code was changed by the specialists.

## Strategy constraint

Do **not** add broad new end-user product functions in the next train. Orvo already has enough surface for the current wedge:

- D2C ecommerce operations control plane;
- deterministic reports;
- Operational Cases;
- evidence snapshots/projections;
- internal operator API, JQL-lite views, and case actions;
- WhatsApp owner briefs;
- Meta Cloud WhatsApp dispatch and delivery-status observability.

Expansion now means making these surfaces safer, more coherent, easier to certify, easier to sell honestly, and easier for autonomous workers to extend without bypassing platform contracts.

## Current risk

### 1. Delivery-status observability landed without a certification matrix

`f147627` added Meta WhatsApp delivery-status ingestion, append-only storage, redaction, docs, and an internal inspection endpoint. This is the right hardening direction because Meta Graph API acceptance is not the same as `sent`, `delivered`, `read`, or provider `failed` lifecycle.

**Risk:** release docs do not yet classify delivery-status ingestion as implemented vs certified vs pilot-ready vs owner-facing-enabled. Operators can inspect status events, but the repo does not yet provide a certified business/run/message correlation story.

### 2. Delivery statuses are not yet correlated to dispatch outcomes by business/run

`app/brain/delivery_status.py` stores provider, message id, status, recipient id, optional business id, timestamp, and redacted raw payload. Current parser paths do not populate business id from Meta status payloads. Run ledger dispatch outcomes can contain `message_id`, but there is no documented/tested read-side join from delivery-status rows to `run_id`, `business_id`, or message type such as `daily_report` vs `owner_case_brief`.

**Risk:** an operator can answer “Meta sent a status event for this message id,” but not reliably “ARTEMEA run X's owner brief was delivered/read/failed” without manual correlation.

### 3. Owner case brief dispatch policy is still implicit

Current scheduled/forced flows can call `record_pipeline_success(...)` with `dispatch_owner_case_brief(...)`, allowing a daily report dispatch plus an `owner_case_brief` secondary dispatch. Recent owner brief work improved case age and acknowledged markers, but the release contract still needs an explicit state.

**Risk:** code reachability may be mistaken for live pilot approval. Owner case briefs should be exactly one of `dry_only`, `explicit_flag_gated`, or `pilot_approved_live` in the decision log and integration train.

### 4. Two WhatsApp send stacks remain in the repo

Brain dispatch uses `app/brain/delivery.py` and `app/brain/dispatch.py` with Meta Cloud/Twilio selection and safer error redaction. `server.py` still contains a separate legacy `_send(...)` path for inbound WhatsApp responses.

**Risk:** credentials, redaction, provider error handling, and delivery-status interpretation can drift between Brain dispatch and legacy chatbot/webhook behavior.

### 5. `execution_ledger.py` remains the post-run side-effect hotspot

`app/brain/execution_ledger.py` currently coordinates run ledger outcomes, connector outcomes, artifacts, case mutation, owner brief construction/dispatch, dispatch outcome recording, failure finalization, and stale-data case creation.

**Risk:** future fixes to delivery, cases, or ledger behavior will collide in one central file and accidentally change unrelated side effects.

### 6. Current-vs-target module ownership remains ambiguous

Docs and worker packets still reference future nested package paths while current authority is mostly flat:

- `app/brain/runtime.py`;
- `app/brain/connector_registry.py`;
- `app/brain/run_ledger.py`;
- `app/brain/execution_ledger.py`;
- `app/brain/operational_cases.py`;
- `app/brain/operator_api.py`;
- `app/brain/operator_views.py`;
- `app/brain/reporting.py`;
- `app/brain/dispatch.py`;
- `app/brain/delivery.py`;
- `app/brain/delivery_status.py`;
- `server.py`;
- `scripts/run_orvo_brain_reports.py`.

**Risk:** autonomous workers may create duplicate package structures or reimplement service logic instead of hardening the current source of truth.

### 7. Operational Case identity still has copy-derived seams

`app/brain/operational_cases.py` has improved metric-registry integration, but some case-family mapping still depends on insight title/text patterns.

**Risk:** harmless Spanish copy changes can alter workflow identity, dedupe, or owner-facing behavior.

### 8. Tiendanube pilot packaging is ahead of some pilot-operable evidence gates

Product/GTM docs position the Tiendanube Exception Desk around evidence-backed cases, daily WhatsApp briefs, and follow-up state. Current implementation still has gaps around SKU/product-level stock evidence, forced-vs-scheduled Tiendanube parity, owner-facing case allowlists, and delivery-status correlation.

**Risk:** Orvo can sell the right wedge, but only after the readiness checklist prevents unsupported claims such as SKU-level stock risk or delivered/read certainty before those gates are green.

### 9. Worktree and integration-queue hygiene is drifting

Org docs require external worktrees under `/root/orvo-agent-worktrees/<task-slug>`, but active worktree inventory includes non-compliant locations under `/root/orvo-agent/.worktrees/*`, `/root/.worktrees/*`, `/tmp/*`, and other root-level paths. There are also many active branches touching central control-plane surfaces.

**Risk:** integration decisions become invisible, central-file conflicts compound, and parent-repo hygiene can be undermined by stale or misplaced autonomous worktrees.

### 10. Pilot state remains internal rehearsal, not live paid-pilot green

The previous council's warning about repo-local ignored operational state remains relevant. The current repo contains ignored operational artifacts such as a local SQLite DB path; this synthesis did not inspect secret values.

**Risk:** live paid pilot remains no-go until secret-bearing local artifacts are sanitized/moved, tokens rotated if real, and delivery/case/evidence gates pass.

## Structural recommendation

### A. Make the next train a certification/reconciliation train

Do not broaden product scope. The next train should classify current surfaces as:

- `implemented`;
- `certified`;
- `pilot_ready`;
- `owner_facing_enabled`;
- `blocked`;
- `parked/non_goal`.

Apply the matrix to daily report dispatch, owner case briefs, Meta Cloud dispatch, WhatsApp delivery statuses, public preview/report endpoints, run ledger, Operational Cases, evidence projections, operator API routes, JQL-lite views, and active autonomous branches.

### B. Treat WhatsApp delivery statuses as observability until correlated

Delivery-status events should remain append-only and idempotent. They should not mutate terminal run records or case lifecycle. The safe next architecture is a read-side certification projection:

```text
RunRecord.dispatch_outcomes[].message_id
  + whatsapp_delivery_status_events.message_id
  -> business/run/message delivery-status projection
```

The projection should answer:

- which business/run/message type produced the message id;
- whether the dispatch pipeline accepted/sent/skipped/failed;
- latest provider lifecycle status;
- provider lifecycle timestamps;
- redacted provider failure metadata;
- whether provider status is `unknown`/`pending` rather than falsely successful.

### C. Explicitly decide owner case brief delivery state

Owner case brief delivery must be documented and enforced as exactly one of:

1. `dry_only`;
2. `explicit_flag_gated`;
3. `pilot_approved_live`.

Recommendation: default to `explicit_flag_gated` or `dry_only` until correlation, idempotency, owner-facing allowlists, and golden projection tests are green.

### D. Publish a current-vs-target bounded-context ownership map

Keep current flat modules authoritative until explicit migration packets land. Target nested package paths should be labels for future extraction, not default worker destinations.

| Context | Current source of truth | Target extraction path | Immediate rule |
|---|---|---|---|
| Runtime & orchestration | `runtime.py`, `runner.py`, `pipeline.py`, `scripts/run_orvo_brain_reports.py`, parts of `execution_ledger.py` | `app/brain/runtime/*` | no broad package migration yet |
| Connectors & ingestion | `connector_registry.py`, `adapters/*`, connector branches in `pipeline.py` | `app/brain/connectors/*` | registry execution wrappers before connector breadth |
| Semantics & insights | `models.py`, `insights.py`, `semantics/metric_registry.py` | `app/brain/semantics/*` | metric registry is semantic source |
| Cases & workflow | `operational_cases.py` | `app/brain/cases/*` | v0 lifecycle only until contract/tests say otherwise |
| Projections & delivery | `reporting.py`, `dispatch.py`, `delivery.py`, `delivery_status.py`, `operator_api.py`, `operator_views.py`, `server.py` | `app/brain/projections/*`, `app/brain/operator_api/*` | projections/statuses are not source of truth |
| Trust / audit / observability | `security/redaction.py`, `run_ledger.py`, `storage.py`, delivery-status stores | `app/brain/security/*`, `app/brain/audit/*` | redaction, ledger, and correlation invariants first |

### E. Add service seams before any package migration

Do not rearrange directories first. Instead, define separable services around the current flat modules:

```text
RuntimeExecutionService
  -> RunLedgerRecorder
  -> ConnectorOutcomeRecorder
  -> CaseMutationService
  -> ProjectionBuilder
  -> DispatchPolicy / DispatchOutbox
  -> DeliveryStatusIngestionService
  -> DeliveryStatusProjectionService
```

The near-term goal is explicit side effects and tests, not a broad package migration.

### F. Replace copy-derived case identity with deterministic `CaseCandidate`

Target flow:

```text
registered metric/evidence inputs
  -> deterministic detection rule
  -> CaseCandidate(case_family, entity_scope, metric_refs, dedupe_parts, severity, evidence_refs)
  -> OperationalCase upsert/update
  -> report / owner brief projection
```

Report text and owner brief copy may change without changing case family or dedupe identity.

### G. Split Hito0 continuity from Tiendanube paid-pilot readiness

Treat these as separate readiness tracks:

1. **Hito0 / ARTEMEA continuity:** preserve existing runtime/report behavior, Google Sheets compatibility, dry-run/forced/scheduled report compatibility, and current owner brief improvements.
2. **Tiendanube Exception Desk paid pilot:** require stricter gates before charging or live owner-facing use: SKU-level stock evidence, forced/scheduled parity, data-stale suppression, owner-facing allowlist, delivery-status correlation, and operator inspectability.

## Exact repo artifacts to update

### Create

- `docs/organization/2026-05-26-control-plane-certification-train.md`
  - surface/packet disposition;
  - implemented/certified/pilot-ready/owner-facing-enabled matrix;
  - owner case brief delivery state;
  - Meta delivery-status observability state.
- `docs/organization/integration-queue.md`
  - branch, worktree, SHA, files, tests, bounded context, review state, conflict risks, merge order, promotion decision.
- `docs/organization/decision-log.md`
  - owner brief delivery decision;
  - delivery-status interpretation;
  - current-vs-target module policy;
  - pilot readiness state;
  - certification-train scope freeze.
- `docs/architecture/bounded-context-ownership-map.md`
  - current module -> bounded context -> target path -> owner lane -> allowed dependents -> migration blocker -> required tests.
- Later QA packet: `tests/golden/test_brain_reporting_golden.py`.
- Later QA packet: `tests/fixtures/golden/`.

### Modify

- `docs/README.md`
  - link the current-vs-target bounded-context map.
- `docs/specs/integration-train-contract.md`
  - reconcile dry-projection wording with current owner-brief dispatch reachability;
  - add owner-facing promotion gate;
  - add delivery-status observability as not equivalent to approval.
- `docs/organization/d2c-worker-task-packets.md`
  - add current dispositions for existing packets/surfaces;
  - mark future package paths as future extraction;
  - add certification/hardening packets before feature work.
- `docs/organization/d2c-autonomous-worker-addendum.md`
  - add certify-existing-surfaces-first rule;
  - add central-file sequencing rule;
  - reinforce external-worktree-only policy.
- `docs/specs/worker-handoff-manifest.md`
  - add release-decision, side-effect, bounded-context owner, promotion-gate, and integration-queue fields.
- `docs/operability/worktree-hygiene.md`
  - explicitly flag `/root/orvo-agent/.worktrees/*`, `/root/.worktrees/*`, `/tmp/*`, and ad hoc root-level worktrees as non-compliant or assign cleanup/migration action.
- `docs/architecture/phase-a-control-plane-contract.md`
  - add current-vs-target warning and service-seam map.
- `docs/adr/0001-control-plane-bounded-contexts-and-module-ownership.md`
  - align current flat modules with target bounded contexts and include `delivery_status.py`.
- `docs/specs/run-ledger-foundation.md`
  - add delivery-status correlation and ambiguous/pre-dispatch failure provenance requirements.
- `docs/specs/internal-operator-api-contract.md`
  - distinguish implemented v0 routes from target routes;
  - document delivery-status endpoint/projection contract.
- `docs/specs/tenant-secret-redaction-contract.md`
  - add webhook/status payload persistence and public/internal response redaction rules.
- `docs/specs/testing-invariant-matrix.md`
  - add owner-brief dispatch policy, delivery-status correlation, signed webhook, duplicate status ingestion, golden projection, and owner-claim allowlist checks.
- `docs/specs/operational-case-engine-contract.md`
  - distinguish implemented v0 lifecycle from target lifecycle;
  - add deterministic `CaseCandidate` seam.
- `docs/specs/d2c-case-family-catalog.md`
  - keep SKU-level `stockout_risk` requirement as the pilot gate;
  - add owner-facing promotion/allowlist rule by pilot tier.
- `docs/specs/d2c-operator-surface-contract.md`
  - align statuses/actions/owner brief claims with current v0 implementation.
- `docs/orvo-brain-runtime.md`
  - link delivery-status operations into pilot runbooks;
  - distinguish hardened Brain dispatch from legacy inbound bot send path;
  - document owner-brief live-send gate.
- `docs/ops/d2c-pilot-readiness-checklist.md`
  - top-level state: internal rehearsal only until gates pass;
  - add delivery-status webhook/correlation gate;
  - add forced-vs-scheduled parity gate;
  - add owner-facing allowlist gate;
  - add local secret-bearing DB/artifact no-go.
- `docs/ops/d2c-pilot-runbook.md`
  - add daily operator steps for run ledger, case queue, dispatch outcome, message id, and delivery statuses;
  - add incident paths for missing/failed provider delivery status and forced/scheduled mismatch.
- `docs/roadmap/d2c-control-plane-roadmap.md`
  - update Milestone 4 with readiness/no-go gates, not product breadth.
- `docs/gtm/2026-05-25-orvo-first-paid-product-pricing-packaging.md`
  - keep paid-pilot messaging conditional on SKU evidence, forced/scheduled parity, owner-brief policy, and delivery-status gates.
- `docs/product/tiendanube-exception-desk-opportunity-spec.md`
  - distinguish current aggregate stock path from required SKU evidence/dedupe gate;
  - keep fulfillment/Meta Ads as later or internal-only until truth gates pass.

## Implementation packets

### Packet CH-1 — Certification train and decision log docs

**Goal:** make current surface state impossible to misread.

**Files:**

- Create: `docs/organization/2026-05-26-control-plane-certification-train.md`
- Create: `docs/organization/integration-queue.md`
- Create: `docs/organization/decision-log.md`
- Modify: `docs/specs/integration-train-contract.md`
- Modify: `docs/organization/d2c-worker-task-packets.md`
- Modify: `docs/ops/d2c-pilot-readiness-checklist.md`

**Acceptance gates:**

- Every active/recent surface has a disposition.
- Owner case brief delivery is exactly `dry_only`, `explicit_flag_gated`, or `pilot_approved_live`.
- Delivery-status ingestion is classified as observability until correlation is certified.
- Implemented/certified/pilot-ready/owner-facing-enabled are separate columns.
- No code changes.

### Packet CH-2 — Current-vs-target bounded-context ownership map

**Goal:** prevent duplicate package/service implementations.

**Files:**

- Create: `docs/architecture/bounded-context-ownership-map.md`
- Modify: `docs/adr/0001-control-plane-bounded-contexts-and-module-ownership.md`
- Modify: `docs/architecture/phase-a-control-plane-contract.md`
- Modify: `docs/README.md`
- Modify: `docs/organization/d2c-worker-task-packets.md`

**Acceptance gates:**

- Every current flat module maps to one primary bounded context.
- Future nested package paths are labelled future-only.
- Central files have sequencing notes.
- `delivery_status.py` is explicitly mapped to delivery/observability.

### Packet CH-3 — Owner brief dispatch policy/idempotency certification

**Goal:** prevent accidental secondary live WhatsApp delivery while preserving daily report compatibility.

**Files:**

- `app/brain/dispatch.py`
- `app/brain/execution_ledger.py`
- `app/brain/runner.py`
- `scripts/run_orvo_brain_reports.py`
- `tests/test_brain_dispatch.py`
- `tests/test_brain_runner.py`
- `tests/test_run_orvo_brain_reports_script.py`
- `docs/specs/integration-train-contract.md`
- `docs/ops/d2c-pilot-readiness-checklist.md`

**Acceptance gates:**

- Owner case brief dispatch is disabled/dry-only by default or requires explicit config/flag.
- Daily report dispatch remains backward-compatible.
- Daily and owner brief idempotency keys remain separate.
- Skipped-by-policy, sent, duplicate-skipped, and failed secondary dispatch are recorded safely and redacted.

### Packet CH-4 — Delivery-status correlation projection

**Goal:** connect Meta provider lifecycle status to business/run/message observability without changing workflow truth.

**Files:**

- `app/brain/delivery_status.py`
- `app/brain/run_ledger.py`
- `app/brain/operator_api.py`
- `server.py`
- `tests/test_brain_whatsapp_delivery_status.py`
- `tests/test_server_whatsapp_delivery_status.py`
- `tests/test_internal_operator_api.py`
- `docs/specs/run-ledger-foundation.md`
- `docs/specs/internal-operator-api-contract.md`

**Acceptance gates:**

- Status events can be queried by `message_id` and projected against dispatch outcomes.
- Business/run/message-type correlation is documented and tested where data exists.
- Unknown/unmatched statuses remain append-only observability, not workflow state.
- Missing provider lifecycle status returns explicit `unknown`/`pending`, not false success.
- Provider failure metadata is redacted.
- Terminal run records are not mutated by late status webhooks.

### Packet CH-5 — Signed webhook and dedupe/count certification

**Goal:** certify production webhook safety and duplicate retry semantics.

**Files:**

- `server.py`
- `app/brain/delivery_status.py`
- `tests/test_server_whatsapp_delivery_status.py`
- `tests/test_brain_whatsapp_delivery_status.py`

**Acceptance gates:**

- With `WHATSAPP_APP_SECRET` configured, valid `X-Hub-Signature-256` persists status events.
- Invalid, missing, and malformed signatures return 401 and do not persist events.
- Status-only signed payload does not trigger inbound message buffering or legacy bot sends.
- `record_events()` semantics are explicit; if observability reports inserted count, duplicates return zero inserted.
- Duplicate webhook retries remain idempotent.

### Packet CH-6 — Legacy WhatsApp send stack separation

**Goal:** keep Brain dispatch hardening from drifting against legacy inbound bot behavior.

**Files:**

- `server.py`
- `app/brain/delivery.py`
- `tests/test_brain_delivery.py`
- `tests/test_server_whatsapp_delivery_status.py`
- `docs/orvo-brain-runtime.md`

**Acceptance gates:**

- Brain dispatch and legacy inbound bot send paths are documented separately or routed through a shared safe transport wrapper.
- Provider errors are redacted on both paths.
- Delivery status ingestion remains independent from inbound chatbot response sending.
- No new product-facing inbox feature is introduced.

### Packet CH-7 — Split post-run side-effect seams

**Goal:** reduce `execution_ledger.py` coupling without broad package migration.

**Files:**

- `app/brain/execution_ledger.py`
- optionally a new flat module such as `app/brain/post_run_services.py`
- `tests/test_brain_runner.py`
- `tests/test_brain_run_ledger.py`
- `tests/test_run_orvo_brain_reports_script.py`

**Acceptance gates:**

- Run ledger recording, case mutation, projection dispatch, and failure handling are separately testable.
- No behavior change to successful daily report dispatch.
- Owner brief policy from Packet CH-3 is respected.
- Failed-run summaries remain redacted.

### Packet CH-8 — Deterministic `CaseCandidate` seam

**Goal:** stop deriving workflow identity from rendered copy.

**Files:**

- `app/brain/operational_cases.py`
- `app/brain/insights.py`
- `app/brain/semantics/metric_registry.py`
- `tests/test_brain_operational_cases.py`
- `tests/test_brain_insights.py`
- `docs/specs/operational-case-engine-contract.md`
- `docs/specs/d2c-case-family-catalog.md`

**Acceptance gates:**

- Changing insight title/explanation/recommended-action copy does not change case family or dedupe identity.
- Existing owner-facing wording remains compatible.
- No new case families.

### Packet CH-9 — Golden owner/operator projection evals

**Goal:** certify existing projections before pilot.

**Files:**

- Create: `tests/golden/test_brain_reporting_golden.py`
- Create: `tests/fixtures/golden/`
- Modify only if tests expose bugs: `app/brain/reporting.py`, `app/brain/operator_api.py`
- Modify: `docs/specs/testing-invariant-matrix.md`

**Acceptance gates:**

- Fixtures cover healthy, degraded, stale/unauthorized, truncated queue, sales drop, stockout risk, no open cases, acknowledged marker, case age marker, and delivery-status caveat.
- Volatile ids/timestamps are normalized only.
- Evidence/source/caveat text is preserved.
- No raw secret-shaped strings appear in golden outputs.

### Packet CH-10 — Tiendanube forced/scheduled parity and SKU evidence gates

**Goal:** make pilot preflight truth checks match scheduled behavior before paid pilot claims.

**Files:**

- `app/brain/pipeline.py`
- `scripts/run_orvo_brain_reports.py`
- `app/brain/adapters/tiendanube.py`
- `app/brain/operational_cases.py`
- `tests/test_run_orvo_brain_reports_script.py`
- `tests/test_brain_pipeline.py`
- `tests/test_brain_tiendanube_*`
- `tests/test_brain_operational_cases.py`
- `docs/ops/d2c-pilot-readiness-checklist.md`

**Acceptance gates:**

- Forced and scheduled Tiendanube runs use compatible report/case behavior and business thresholds.
- Ledger metadata never implies success for unexecuted connectors.
- SKU/product stock evidence and dedupe match the case-family catalog before owner-facing stockout claims.
- Stale/missing stock suppresses stockout claims and opens/updates `data_stale` instead.

### Packet CH-11 — Owner-facing case allowlist/readiness gate

**Goal:** prevent internal, conditional, or future case families from leaking into WhatsApp owner briefs.

**Files:**

- `app/brain/reporting.py`
- `app/brain/dispatch.py`
- `app/brain/operational_cases.py`
- `tests/test_brain_reporting.py`
- `tests/test_brain_dispatch.py`
- `docs/specs/d2c-case-family-catalog.md`

**Acceptance gates:**

- Pilot owner brief includes only owner-facing-ready families: `data_stale`, certified SKU-level `stockout_risk`, and conservative configured `sales_drop` if enabled.
- `fulfillment_backlog`, `spend_without_orders`, `channel_mix_shift`, and `unanswered_conversations` remain hidden unless explicitly promoted.
- Hidden cases remain inspectable internally.
- No unsupported owner-facing claims.

## Non-goals / deferred explicitly

Do **not** start these in the next train:

- broad new end-user product functions;
- new first-pilot connectors;
- Meta Ads/channel-mix owner-facing expansion;
- MercadoLibre owner-facing expansion;
- WhatsApp inbox ingestion as a product surface;
- unanswered-conversation owner-facing cases;
- owner-facing fulfillment backlog before Tiendanube payment/fulfillment truth gates pass;
- saved custom views/dashboard expansion;
- public customer API expansion;
- generic chatbot or generic agent-platform positioning;
- marketplace/developer platform work;
- autonomous external actions on ads, stock, orders, refunds, prices, or customer messages;
- full package migration from flat modules to nested packages;
- UI/report polish that bypasses runtime, registry, ledger, cases, evidence, or audit.

Feature ideas should stay parking-lot unless they directly protect the current D2C control-plane behavior.

## Guardrails

- Keep `/root/orvo-agent` clean; write only in external worktrees under `/root/orvo-agent-worktrees`.
- Do not create/update/remove/schedule cron jobs from this lane.
- Do not push or deploy.
- WhatsApp is projection/delivery/observability, never source of truth.
- Delivery statuses are observability until correlated and certified.
- Reports, briefs, and LLM/copy layers must not create metrics, detections, priorities, lifecycle transitions, or actions.
- Every owner-facing number must trace to deterministic evidence.
- Redact at every boundary: runtime, ledger, cases, artifacts, dispatch, delivery statuses, public errors, internal API, docs/examples, golden fixtures, local operational state.
- Preserve Hito0/ARTEMEA and current daily-report compatibility while hardening.
- Require focused tests plus `pytest -q`, spec review, and quality/safety review before merging code packets.
- Live owner-facing dispatch requires decision-log entry, release gate, idempotency proof, delivery-status observability, owner-facing allowlist, and golden projection coverage.
- Repo-local secret-bearing DB/config artifacts remain live-pilot no-go until sanitized/moved and rotated if real.

## Recommended next implementation packet

Start with **Packet CH-1 — Certification train and decision log docs**.

Reason: it is docs-only, unblocks worker coordination, and prevents current implementation reachability from being mistaken for pilot approval. It should define owner brief delivery state and delivery-status observability state before code workers add more behavior.

After CH-1, dispatch CH-2 (bounded-context ownership map), then CH-4/CH-5 (delivery-status correlation and signed webhook certification), then CH-3 (owner brief dispatch policy) if live-send risk needs immediate enforcement.

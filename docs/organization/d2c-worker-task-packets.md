# D2C Worker Task Packets

Status: Draft worker packet catalog
Date: 2026-05-24
Related: `docs/organization/d2c-autonomous-worker-addendum.md`, `docs/specs/integration-train-contract.md`

## Purpose

These packets are ready-to-dispatch autonomous worker scopes. Each packet is bounded, has source docs, and avoids overlapping edits where possible.

## Common preamble

Every worker gets:

```text
Orvo's first sellable product is a D2C ecommerce control plane for Tiendanube/WhatsApp-first operators. Build internally as platform/control-plane: compiled runtime, connector registry, run ledger, metric registry, Operational Cases, audit/governance, and operator surfaces. Do not build chatbot shortcuts or bypass runtime/registry/ledger/cases/audit.
```

## Packet A — Redaction invariant foundation

Goal: implement shared redaction helper and tests.

Read:

- `docs/specs/tenant-secret-redaction-contract.md`
- `docs/specs/testing-invariant-matrix.md`

Likely files:

- `app/brain/security/redaction.py`
- `tests/invariants/test_secret_redaction.py`

Acceptance:

- representative secret strings redacted;
- no existing tests broken;
- no new dependency unless justified.

## Packet B — Compiled runtime model

Goal: add `CompiledBusinessRuntime` Pydantic model and serialization/hash tests.

Read:

- `docs/specs/compiled-runtime-contract.md`
- `docs/architecture/phase-a-control-plane-contract.md`

Likely files:

- `app/brain/runtime/compiled.py`
- `tests/contracts/test_compiled_runtime_contract.py`

Acceptance:

- deterministic hash;
- secret refs only;
- no execution side effects.

## Packet C — Connector registry wrapper

Goal: add registry specs for current connectors without rewriting adapters.

Read:

- `docs/specs/connector-registry-contract.md`
- `docs/specs/metric-registry-contract.md`

Likely files:

- `app/brain/connectors/contracts.py`
- `app/brain/connectors/registry.py`
- `tests/contracts/test_connector_registry_contract.py`

Acceptance:

- Tiendanube/google_sheets/csv registered;
- emitted families declared;
- invalid config fails before runtime.

## Packet D — Run ledger storage

Goal: add idempotent ledger tables and storage helpers.

Read:

- `docs/specs/storage-migration-contract.md`
- `docs/specs/run-ledger-foundation.md`

Likely files:

- `app/brain/storage.py`
- `tests/contracts/test_run_ledger_storage_contract.py`

Acceptance:

- migrations run twice;
- old storage/report behavior preserved;
- artifacts redacted before storage.

## Packet E — Runtime compiler shim

Goal: compile existing business config into runtime plan and validate connector registry.

Read:

- `docs/specs/compiled-runtime-contract.md`
- `docs/specs/connector-registry-contract.md`

Likely files:

- `app/brain/runtime/compiler.py`
- `tests/contracts/test_runtime_compiler_contract.py`

Acceptance:

- compile preview executes no connectors;
- invalid connector config fails deterministically;
- runtime hash stable.

## Packet F — Operator API read-only skeleton

Goal: add internal read-only endpoints for compile preview/readiness/run history once underlying storage exists.

Dependency: dispatch Packet F only after runtime compiler, connector registry, run ledger storage, metric registry, and case engine basics are available for the endpoints it exposes. Before those dependencies land, workers may only implement compile-preview/readiness projections and must not fake run/case state.

Read:

- `docs/specs/internal-operator-api-contract.md`
- `docs/specs/tenant-secret-redaction-contract.md`

Likely files:

- `server.py` or internal router module;
- `tests/test_server_brain*.py` or `tests/contracts/test_operator_api_contract.py`.

Acceptance:

- responses use envelope;
- business scoped;
- redacted;
- no external dispatch.

## Packet G — Metric registry v0

Goal: define canonical metrics and legacy aliases for existing report/case behavior.

Read:

- `docs/specs/metric-registry-contract.md`
- `docs/specs/d2c-case-family-catalog.md`

Likely files:

- `app/brain/semantics/metric_registry.py`
- `tests/contracts/test_metric_registry_contract.py`

Acceptance:

- current metrics resolve through aliases;
- unknown metrics fail in strict mode;
- first case families have registered metric refs.

## Packet H — Case engine v0

Goal: implement deterministic open/update/dedupe lifecycle for first case families after metrics exist.

Read:

- `docs/specs/operational-case-engine-contract.md`
- `docs/specs/d2c-case-family-catalog.md`

Likely files:

- `app/brain/cases/models.py`
- `app/brain/cases/engine.py`
- `app/brain/cases/storage.py`
- `tests/contracts/test_operational_case_contract.py`

Acceptance:

- `sales_drop`, `stockout_risk`, `data_stale` lifecycle tests;
- no LLM decision path;
- evidence required.

## Packet I — Metric registry adoption gate

Goal: use the semantic metric registry as the advisory validation layer for current case/report inputs before promoting any strict runtime behavior.

Dependency: dispatch after Packet G and after existing compatibility tests are green.

Read:

- `docs/specs/metric-registry-contract.md`
- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/integration-train-contract.md`

Likely files:

- `app/brain/semantics/metric_registry.py`
- `app/brain/operational_cases.py`
- `app/brain/reporting.py`
- `tests/contracts/test_metric_validation_contract.py`
- `tests/test_brain_operational_cases.py`

Acceptance:

- legacy metric aliases still resolve;
- unknown metric behavior is advisory unless explicitly strict;
- no owner-facing wording changes;
- full suite remains green.

## Packet J — Evidence snapshot canonicalization

Goal: make evidence snapshots the canonical case/timeline reference for operator projections and persisted case history.

Dependency: dispatch after case engine basics and operator case actions/comments are green.

Read:

- `docs/specs/operational-case-engine-contract.md`
- `docs/specs/internal-operator-api-contract.md`
- `docs/specs/tenant-secret-redaction-contract.md`

Likely files:

- `app/brain/operational_cases.py`
- `app/brain/operator_api.py`
- `tests/test_brain_operational_cases.py`
- `tests/test_internal_operator_api.py`

Acceptance:

- timeline events reference persisted canonical snapshot IDs;
- duplicate detections reuse/update canonical snapshots instead of creating ambiguous refs;
- raw SQLite/store reload tests prove secret-shaped refs and actor values are redacted before persistence.

## Packet K — Case-backed brief dry projection

Goal: create a dry owner/operator brief projection from actionable Operational Cases without enabling automatic WhatsApp delivery.

Dependency: dispatch after Packet J so projection cites canonical evidence.

Read:

- `docs/product/report-design.md`
- `docs/specs/operational-case-engine-contract.md`
- `docs/specs/integration-train-contract.md`

Likely files:

- `app/brain/reporting.py`
- `app/brain/operator_api.py`
- `tests/test_brain_reporting.py`
- `tests/test_internal_operator_api.py`

Acceptance:

- resolved cases are excluded;
- evidence freshness/degraded state is explicit;
- truncation preserves truthful total open-case count;
- no WhatsApp send path changes.

## Packet L — Operator search/view hardening

Goal: harden read-only built-in case views and JQL-lite query behavior before saved views or writable filters exist.

Read:

- `docs/specs/internal-operator-api-contract.md`
- `docs/specs/integration-train-contract.md`

Likely files:

- `app/brain/operator_views.py`
- `app/brain/operator_api.py`
- `server.py`
- `tests/test_operator_case_views.py`
- `tests/test_internal_operator_api.py`

Acceptance:

- built-in views match equivalent direct queries;
- route/context owns business scope;
- SQL-looking input is rejected before storage;
- response/error envelopes are redacted and stable.

## Packet M — Pilot-readiness runbook refresh

Goal: update pilot operating docs so the Tiendanube/WhatsApp-first checklist matches actual runtime, ledger, case, evidence, and operator-comment capabilities.

Read:

- `docs/ops/d2c-pilot-readiness-checklist.md`
- `docs/specs/integration-train-contract.md`
- `docs/roadmap/d2c-control-plane-roadmap.md`

Likely files:

- `docs/ops/d2c-pilot-readiness-checklist.md`
- `docs/roadmap/d2c-control-plane-roadmap.md`
- `docs/specs/integration-train-contract.md`

Acceptance:

- docs link to real implemented surfaces only;
- WhatsApp remains a projection/delivery surface, not source of truth;
- docs validation and secret scan pass.

## Packet N — `channel_mix_shift` promotion gate

Goal: promote `channel_mix_shift` from catalog/deferred design target into an implemented owner-facing case family, or explicitly keep it hidden if channel-scoped evidence is not ready.

Dependency: dispatch only after Metric registry v0, case evidence snapshots, and cross-source freshness behavior are green. This packet must not be combined with unrelated operator API or connector rewrites.

Read:

- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/metric-registry-contract.md`
- `docs/specs/testing-invariant-matrix.md`
- `docs/architecture-reviews/2026-05-30-post-merge-architecture-review.md`

Likely files:

- `app/brain/semantics/metric_registry.py`
- `app/brain/operational_cases.py`
- `tests/contracts/test_metric_registry_contract.py`
- `tests/test_brain_operational_cases.py`

Acceptance:

- decision is explicit: either `channel_mix_shift` remains deferred/internal, or it is added to `CASE_FAMILY_METRICS` with registered `case_allowed=true` metric refs;
- no owner-facing `channel_mix_shift` is emitted from aggregate-only revenue/order metrics;
- missing or stale channel sources suppress the case or create/update `data_stale`;
- dedupe/entity-scope tests prove one all-channel key cannot hide distinct channel-specific issues;
- full suite remains green.

## Packet O — Trust/Admin/Security audit closure

Goal: close the 2026-05-31 and 2026-06-01 architecture-review blockers before presenting Trust/Admin/Security as live-use ready.

Dependency: dispatch after the current internal operator API action path is green. Do not combine with unrelated workflow or connector rewrites.

Current source-of-truth check: the 2026-06-01 Architecture Review Board re-confirmed that current HEAD has role helpers but no durable `operator_audit` module/store. The narrow `/internal/brain/whatsapp/delivery-statuses` `INTERNAL_READ_PERMISSION` gap was closed by `b4f8240`; the remaining blocker is durable audit/least-privilege hardening before adding more operator surfaces.

Read:

- `docs/architecture-reviews/2026-05-31-review.md`
- `docs/architecture-reviews/2026-06-01-architecture-board-review.md`
- `docs/specs/internal-operator-api-contract.md`
- `docs/specs/tenant-secret-redaction-contract.md`
- `docs/specs/testing-invariant-matrix.md`

Likely files:

- `server.py`
- `app/brain/operator_api.py`
- `app/brain/storage.py`
- `tests/test_internal_operator_api.py`

Acceptance:

- failed/denied case actions are audited where an authenticated actor/business/case context can be derived;
- auth failures are either audited through a safe pre-auth event shape or explicitly documented as impossible without a trusted actor/business context;
- audit payloads and actor/business/target fields are redacted before persistence;
- every internal operator route, including `/internal/brain/whatsapp/delivery-statuses`, enforces the relevant role permission and has a regression test for viewer/operator/admin behavior;
- minimal action-scope/RBAC behavior is implemented, or the branch is explicitly labeled audit-foundation-only;
- full suite remains green.

## Packet P — Work-management lifecycle regression cleanup

Status: mostly satisfied in the current baseline; dispatch only as a narrow regression/fixer packet if tests or review show one of these invariants has drifted. Do **not** merge or revive the stale `codex/work-management` branches wholesale; the 2026-06-02 Architecture Review Board marked them selective-salvage/likely-superseded because their tree shape predates the current operator API package split and current control-plane files.

Goal: keep merged lifecycle behavior aligned with the Operational Case contract while separating registry/Jira-parity work into Packet S.

Dependency: current internal operator case-action path and `tests/test_internal_operator_api.py` / `tests/test_brain_operational_cases.py` are green. If those tests already prove the invariant, update docs/reports rather than rewriting code.

Current source-of-truth check:

- `app/brain/operator_api/actions.py` requires a non-empty reason for terminal actions (`resolve_case`, `dismiss_case`).
- `app/brain/operational_cases.py` hardcodes lifecycle transitions and intentionally does not allow direct `open -> resolved`.
- `app/brain/operator_views.py` provides read-only JQL-lite/built-in views over cases, not a canonical workflow registry.

Read:

- `docs/architecture-reviews/2026-06-02-review.md`
- `docs/specs/operational-case-engine-contract.md`
- `docs/specs/d2c-action-key-catalog.md`

Likely files, only if a regression is found:

- `app/brain/operational_cases.py`
- `app/brain/operator_api/actions.py`
- `tests/test_brain_operational_cases.py`
- `tests/test_internal_operator_api.py`

Acceptance:

- terminal actions still require a non-empty reason;
- lifecycle transition tests assert the contract table, including the intentional absence of direct `open -> resolved`;
- project abstraction, issue-type registry/versioning, workflow-definition registry, and status-category work remain Packet S rather than hidden in this cleanup;
- no owner-facing projection changes unless required by the contract.

## Packet Q — Connector registry secret-ref runtime hardening

Goal: move registry-driven daily report execution away from transitional inline secret params before calling the connector platform compiled-runtime complete.

Dependency: dispatch after `codex/connector-platform` is present and current connector compatibility tests are green.

Read:

- `docs/architecture-reviews/2026-05-31-review.md`
- `docs/specs/connector-registry-contract.md`
- `docs/specs/compiled-runtime-contract.md`
- `docs/specs/tenant-secret-redaction-contract.md`

Likely files:

- `app/brain/connector_registry.py`
- `app/brain/runtime.py`
- `app/brain/pipeline.py`
- `tests/test_brain_connector_registry.py`
- `tests/test_brain_pipeline.py`

Acceptance:

- required secret refs resolve at execution time without entering runtime hashes;
- Tiendanube/MercadoLibre/Meta Ads legacy inline token paths are either removed or explicitly isolated as compatibility shims with redaction tests;
- connector factory imports remain static/allowlisted and not tenant-controlled;
- missing/invalid secrets produce redacted typed failures and, where runtime/case integration exists, open/update `data_stale` instead of unsupported advice.

## Packet R — Connector/semantic family alignment gate

Goal: prevent drift between connector-declared `emitted_metric_families` and the semantic metric registry.

Dependency: dispatch after current metric registry diagnostics and connector registry tests are green.

Read:

- `docs/specs/connector-registry-contract.md`
- `docs/specs/metric-registry-contract.md`
- `docs/specs/testing-invariant-matrix.md`
- `docs/specs/d2c-case-family-catalog.md`

Likely files:

- `app/brain/connector_registry.py`
- `app/brain/semantics/metric_registry.py`
- `tests/contracts/test_adapter_metric_emission_contract.py`
- `tests/test_brain_connector_registry.py`

Acceptance:

- tests fail when a connector declares an emitted family absent from the semantic registry;
- connector emission/report/case metric validation uses one canonical family vocabulary or shared constants;
- `channel_mix_shift` remains deferred/internal unless Packet N acceptance gates are also satisfied;
- no new dependency and no owner-facing wording changes.

## Packet S — WorkItem envelope and status-category projection

Status: satisfied in the current baseline; dispatch only as a narrow regression/fixer packet if WorkItem projection invariants drift. Do **not** revive older status-category/JQL branches that use `todo` or add a second work-item lifecycle store.

Goal: keep the shipped Jira-like work-management projection layer aligned without rewriting `OperationalCase` or making manually-created work the source of truth for deterministic cases.

Dependency: dispatch after current case-action, built-in view, and JQL-lite tests are green, and after Packet P is confirmed satisfied or explicitly unnecessary. This packet is a thin registry/projection/schema slice; it must not change case detection, case storage semantics, lifecycle transitions, or owner-facing WhatsApp/report copy.

Current source-of-truth check:

- `app/brain/work_items.py` now exposes project/work-item projections, deterministic project keys with a hash suffix for long names, issue-type definitions, workflow/status definitions, and canonical status categories.
- `app/brain/operator_views.py` resolves JQL-lite `project`, `issue_type`, `status_category`, and `assignee_ref` through the WorkItem/OperationalCase helpers.
- `OperationalCase` remains the durable state owner; there is no separate WorkItem persistence table or owner-facing copy change from this slice.

Read:

- `docs/architecture-reviews/2026-06-02-review.md`
- `docs/roadmap/d2c-control-plane-roadmap.md`
- `docs/specs/operational-case-engine-contract.md`
- `docs/specs/internal-operator-api-contract.md`
- `docs/specs/integration-train-contract.md`

Likely files:

- `app/brain/work_items.py` or a similarly narrow projection module
- `app/brain/operational_cases.py` only for exported constants/helpers, not lifecycle rewrites
- `app/brain/operator_api/projections.py` or current package modules, not a restored monolithic `operator_api.py`
- `app/brain/operator_views.py` only after canonical status/category helpers exist
- `tests/test_work_items.py` or focused additions to `tests/test_internal_operator_api.py` / `tests/test_operator_case_views.py`

Acceptance:

- projects remain represented as a projection/envelope over `business_id` with stable, collision-resistant project keys and no tenant-crossing leakage;
- issue/work-item projection includes `work_item_id`, `project_key`, `issue_type`, `status`, `status_category`, priority, assignee/owner, created/updated timestamps, and canonical `case_id` for detected Operational Cases;
- status categories are deterministic (`to_do`, `in_progress`, `done`) and terminal flags match existing `resolved`/`dismissed` behavior;
- workflow/status definition helpers expose the current transition table for projection/validation without enabling tenant-custom workflows yet;
- JQL-lite grows `project`, `status_category`, `assignee_ref`, and `issue_type` fields only after they derive from the canonical projection helpers;
- API/projection callers can read WorkItem-shaped output without bypassing the Operational Case store;
- no new lifecycle transitions, LLM decisions, manual work creation, or owner-facing copy changes are introduced.

## Packet T — Metric registry enforcement for Operational Cases

Goal: promote the semantic metric registry from advisory diagnostics to an enforced gate for deterministic Operational Case creation while keeping previews/imports compatible.

Dependency: dispatch after Packet R connector/semantic family alignment is green and after current CSV/Sheets/Tiendanube compatibility tests pass. Do not combine with connector execution rewrites.

Source-of-truth check: current case evidence uses `default_metric_registry()` and `validate_metrics(..., strict=False)` but stores `metric_registry_mode: advisory`; current report merging still sums duplicate numeric keys or last-wins non-numeric/unit-mismatched keys outside registry-owned aggregation policy.

Read:

- `docs/architecture-reviews/2026-06-01-architecture-board-review.md`
- `docs/specs/metric-registry-contract.md`
- `docs/specs/d2c-case-family-catalog.md`
- `docs/specs/testing-invariant-matrix.md`

Likely files:

- `app/brain/semantics/metric_registry.py`
- `app/brain/operational_cases.py`
- `app/brain/pipeline.py`
- `tests/contracts/test_metric_registry_contract.py`
- `tests/test_brain_operational_cases.py`

Acceptance:

- Operational Case detection rejects, quarantines, or opens/updates `data_stale` for unknown/invalid operational metrics instead of letting them create owner-facing cases;
- enforcement modes are explicit, at minimum separating preview/import advisory behavior from runtime case-creation behavior;
- CSV/Sheets unknown metrics are marked custom/non-operational unless mapped to registered metrics;
- duplicate-key aggregation policy is registry-defined or explicitly blocked for non-aggregatable metrics before cases are created;
- compatibility tests prove legacy aliases still resolve and existing valid Tiendanube/CSV/Sheets reports remain green.

## Packet U — Workflow action ledger and approval object foundation

Status: foundation mostly satisfied in the current baseline; dispatch the next slice only for approval/execution hardening that preserves zero side effects.

Goal: harden durable workflow/action bookkeeping and approval projections before any workflow automation can mutate cases or call external systems.

Dependency: dispatch after Packet O Trust/Admin/Security audit closure and current workflow dry-run tests are green. This packet must keep workflow automation projection-only unless the durable ledger gate is fully implemented and tested.

Current source-of-truth check:

- `app/brain/workflow_action_ledger.py` records durable workflow action ledger rows, enforces idempotency keys, redacts params, and creates approval-request objects for approval-required actions.
- `app/brain/workflow_automation.py` can write planned workflow actions to the ledger while preserving projection-only behavior.
- `app/brain/workflow_approval_queue.py` and `app/brain/workflow_execution_queue.py` expose read-only queue projections with execution disabled and `side_effects_executed = 0`.
- Manual case-action idempotency now covers the internal operator API when callers provide `X-Idempotency-Key`: keys are reserved before mutation, stored as `source="manual_operator"`, and duplicate completed requests replay without a second timeline mutation. Governed external/provider execution remains out of scope unless a separate packet adds provider idempotency, execution-attempt ledgering, retry/failure semantics, and approval-backed side-effect execution.

Read:

- `docs/architecture-reviews/2026-06-01-architecture-board-review.md`
- `docs/specs/d2c-action-key-catalog.md`
- `docs/specs/internal-operator-api-contract.md`
- `docs/specs/storage-migration-contract.md`
- `docs/specs/testing-invariant-matrix.md`

Likely files:

- `app/brain/workflow_automation.py`
- `app/brain/workflow_action_ledger.py`
- `app/brain/workflow_approval_queue.py`
- `app/brain/workflow_execution_queue.py`
- `tests/test_workflow_automation_simulation.py`
- focused operator API/case-action tests only if manual action idempotency is intentionally added.

Acceptance:

- workflow action ledger continues to record action key, case/work item ref, actor/source, idempotency key, approval state, execution state, timestamps, and redacted params;
- duplicate idempotency keys continue to be enforced against durable storage, not only within one dry-run projection;
- approval-required actions continue to produce durable approval requests with deterministic lifecycle states and cannot execute as side effects;
- approval/execution queue projections remain read-only, redacted, business-scoped, and explicit that execution is disabled;
- manual case mutations either accept/enforce idempotency keys or are explicitly documented as non-automated operator actions with audit coverage from Packet O;
- no external side effects are executed and existing dry-run projections remain backward-compatible.

## Packet output format

Workers must report:

- branch/worktree;
- commit SHA;
- files changed;
- tests run;
- product impact;
- platform contract impact;
- risks/blockers;
- parent repo cleanliness.

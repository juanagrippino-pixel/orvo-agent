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

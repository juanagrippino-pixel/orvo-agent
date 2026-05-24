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

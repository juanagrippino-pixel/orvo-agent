# Milestone 1 Runtime/Ledger/Registry Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build the first trustworthy runtime foundation for Orvo's D2C control plane without breaking current reports.

**Architecture:** Additive Phase A implementation. Existing adapters/report paths stay operational while workers introduce `CompiledBusinessRuntime`, connector registry wrappers, run ledger records, redaction invariants, and compatibility tests.

**Tech Stack:** Python, Pydantic v2, SQLite, pytest, existing `app/brain/*` modules.

---

## Source docs to read first

- `CLAUDE.md`
- `docs/architecture/phase-a-control-plane-contract.md`
- `docs/specs/compiled-runtime-contract.md`
- `docs/specs/connector-registry-contract.md`
- `docs/specs/tenant-secret-redaction-contract.md`
- `docs/specs/storage-migration-contract.md`
- `docs/specs/testing-invariant-matrix.md`
- `docs/roadmap/d2c-control-plane-roadmap.md`

## Priority rule

Milestone 1 must make the runtime explainable and safe. Do not start case UI, Meta Ads expansion, or automation before compile/registry/ledger/redaction foundations exist.

## Task 1: Add contract/invariant test directories

**Objective:** Create empty-but-real test homes for future workers.

**Files:**

- Create: `tests/contracts/`
- Create: `tests/invariants/`
- Create: `tests/contracts/test_contract_scaffold.py`
- Create: `tests/invariants/test_invariant_scaffold.py`

**Verification:**

```bash
pytest tests/contracts tests/invariants -q
```

Expected: scaffold tests pass.

## Task 2: Add redaction helper and tests

**Objective:** Centralize basic secret redaction before runtime/ledger artifacts exist.

**Files:**

- Create/modify: `app/brain/security/redaction.py` or nearest existing security module.
- Test: `tests/invariants/test_secret_redaction.py`

**Required behavior:**

- redact bearer tokens;
- redact URL query token params;
- redact fake private keys;
- preserve safe IDs and statuses.

**Verification:**

```bash
pytest tests/invariants/test_secret_redaction.py -q
```

## Task 3: Add `CompiledBusinessRuntime` model

**Objective:** Define serializable runtime model with secret refs only.

**Files:**

- Create: `app/brain/runtime/compiled.py`
- Test: `tests/contracts/test_compiled_runtime_contract.py`

**Required behavior:**

- deterministic hash for same inputs;
- redacted serialization;
- run modes include preview/forced/scheduled/operator_triggered;
- no raw secret fields.

**Verification:**

```bash
pytest tests/contracts/test_compiled_runtime_contract.py -q
```

## Task 4: Add connector registry wrapper

**Objective:** Register current connectors without rewriting adapters.

**Files:**

- Create: `app/brain/connectors/contracts.py`
- Create: `app/brain/connectors/registry.py`
- Test: `tests/contracts/test_connector_registry_contract.py`

**Required behavior:**

- specs for `tiendanube`, `google_sheets`, `csv`;
- Tiendanube emits commerce/runtime families;
- invalid connector type fails deterministically;
- secret refs are references only.

**Verification:**

```bash
pytest tests/contracts/test_connector_registry_contract.py -q
```

## Task 5: Add runtime compiler shim

**Objective:** Compile existing `BusinessConfig`/schedule into runtime plan without executing connectors.

**Files:**

- Create: `app/brain/runtime/compiler.py`
- Test: `tests/contracts/test_runtime_compiler_contract.py`

**Required behavior:**

- validates connector registry entries;
- converts legacy raw connector secret params into redacted/stable secret refs for the compiled artifact, or fails closed;
- produces runtime hash;
- compiled runtime hash/serialization never includes raw legacy secret values;
- includes delivery/artifact/redaction policies;
- compile preview does not execute external API calls.

**Verification:**

```bash
pytest tests/contracts/test_runtime_compiler_contract.py -q
```

## Task 6: Add run ledger storage tables idempotently

**Objective:** Prepare ledger persistence while preserving existing storage behavior.

**Files:**

- Modify: `app/brain/storage.py` or storage extension.
- Test: `tests/contracts/test_run_ledger_storage_contract.py`
- Test: existing storage/report tests.

**Required behavior:**

- migrations run twice;
- old idempotency store still works;
- create run start/end records;
- persist connector outcome and redacted artifact refs.

**Verification:**

```bash
pytest tests/contracts/test_run_ledger_storage_contract.py -q
pytest tests/test_run_orvo_brain_reports_script.py -q
```

## Task 7: Wrap forced/scheduled execution with ledger start/end

**Objective:** Make real runs explainable without changing report content.

**Files:**

- Modify: `scripts/run_orvo_brain_reports.py`
- Modify: `app/brain/runner.py` or execution entrypoint.
- Test: focused runner/script tests.

**Required behavior:**

- forced and scheduled execution call the `CompiledBusinessRuntime` execution path or an explicitly tested compatibility shim;
- preview/forced/scheduled parity is covered by a focused test for the same business/date/config inputs;
- run record created for forced dry run;
- connector health recorded when available;
- dispatch attempt recorded/skipped idempotently;
- existing report output remains compatible.

**Verification:**

```bash
pytest tests/test_run_orvo_brain_reports_script.py -q
pytest -q
```

## Task 8: Add docs/examples update

**Objective:** Document new runtime/ledger behavior without exposing secrets.

**Files:**

- Modify: `docs/orvo-brain-runtime.md`
- Modify/create: `examples/*` only if needed.

**Verification:**

```bash
pytest tests/test_runtime_docs_examples.py -q
git diff --check
```

## Milestone 1 exit criteria

- preview/forced/scheduled are on one compiler path or tested shim;
- Tiendanube registry spec exists;
- run ledger records connector results/artifacts/dispatch attempts;
- secret redaction invariant tests exist and pass;
- existing Hito0/report tests remain green;
- parent repo clean after merge.

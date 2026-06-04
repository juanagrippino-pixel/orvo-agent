# Testing and Invariant Matrix

Status: Draft QA contract
Date: 2026-05-24
Related: `docs/ops/d2c-pilot-readiness-checklist.md`, `docs/specs/compiled-runtime-contract.md`

## Purpose

This matrix defines the test classes workers must add as Orvo moves from report nucleus to D2C control plane. It prevents green-looking branches that only test happy paths.

## Test categories

### Contract tests

Prove public/internal contracts and schemas behave as documented.

Required areas:

- compiled runtime model serialization/redaction;
- connector registry specs;
- metric registry specs and aliases;
- run ledger record shape;
- case lifecycle and action keys;
- internal operator API response envelopes.

### Invariant tests

Prove properties that must always hold.

Required invariants:

- no raw secrets in serialized runtime, ledger, artifacts, API responses, docs examples;
- same config compiles to same runtime hash;
- runtime execution cannot mutate control-plane config silently;
- repeated detection updates existing case rather than creating duplicates;
- stale connector suppresses dependent business claims;
- LLM/copy layer cannot create metrics/cases/actions.

### Compatibility tests

Protect existing behavior.

Required compatibility:

- current Google Sheets report path;
- current CSV preview path;
- current Tiendanube preview/scheduled path;
- current forced script `scripts/run_orvo_brain_reports.py`;
- docs runtime examples;
- idempotency/delivery behavior.

### Golden output tests

Use fixture reports/cases to detect accidental wording/claim changes.

Golden examples:

- healthy Tiendanube daily brief;
- degraded Tiendanube brief;
- sales drop case projection;
- stockout risk case projection;
- stale data caveat.

## Test command policy

For docs-only changes:

```bash
git diff --check
python scripts/validate_docs.py  # if/when available
```

For code changes in runtime/registry/ledger/cases:

```bash
pytest tests/test_run_orvo_brain_reports_script.py -q
pytest tests/test_runtime_docs_examples.py -q
pytest tests/contracts -q
pytest tests/invariants -q
pytest -q
```

If `tests/contracts` or `tests/invariants` does not exist yet, the worker implementing the first relevant feature must create it.

## Promotion gates

A feature cannot become owner-facing unless:

- contract tests pass;
- invariant tests pass;
- compatibility tests pass;
- degraded-state behavior is tested;
- redaction test includes representative secret strings;
- review confirms no duplicate source of truth.

## Review checklist

Reviewers must ask:

1. Does this reuse the compiled runtime/registry/ledger/case path?
2. Does it protect existing Hito0/report behavior?
3. Are all owner-facing numbers evidence-backed?
4. Are stale/degraded paths tested?
5. Are secrets redacted in success and error paths?
6. Are tests deterministic and not API-dependent?

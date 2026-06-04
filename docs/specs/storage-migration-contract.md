# Storage and Migration Contract

Status: Draft implementation contract
Date: 2026-05-24
Related: `docs/specs/compiled-runtime-contract.md`, `docs/specs/operational-case-engine-contract.md`, `docs/specs/run-ledger-foundation.md`

## Purpose

Orvo's first control-plane implementation can stay SQLite-backed, but schema changes must be additive, idempotent, and compatible with the existing report/runtime path.

## Migration principles

- Add tables/columns idempotently.
- Do not rename or drop existing tables in Phase A.
- Keep existing store methods working.
- Prefer JSON columns for early artifacts only when typed model validation exists at the service boundary.
- Every new table needs `business_id` and timestamps unless explicitly global/static.
- New persisted artifacts must be redacted before storage unless they are explicitly private and access-controlled.

## Initial tables

### Runtime / ledger

- `brain_runs`
- `brain_connector_runs`
- `brain_artifacts`
- `brain_dispatch_attempts`
- `brain_run_events`

### Registry snapshots

- `brain_runtime_compilations`
- `brain_connector_registry_versions` optional once registry changes over time
- `brain_metric_registry_versions` optional once registry changes over time

### Cases

- `brain_cases`
- `brain_case_events`
- `brain_case_evidence`
- `brain_case_actions`

### Operator/audit

- `brain_audit_events`
- `brain_operator_actions`

## Required indexes

- `(business_id, created_at)` for runs/events;
- `(business_id, status, updated_at)` for cases;
- unique `(business_id, dedupe_key)` for unresolved cases (`open`, `acknowledged`, `in_progress`) where feasible; resolved/dismissed cases may be reopened by policy rather than duplicated;
- `(run_id)` for connector runs/artifacts/events;
- `(case_id)` for timeline/evidence/actions.

## Backfill rules

When introducing new tables around existing runs:

- do not attempt risky historical reconstruction unless needed;
- mark old runs as `legacy_untracked` if surfaced;
- new runs after migration must write ledger entries;
- compatibility shims may write partial records with explicit `schema_phase`.

## Rollback rules

- Additive tables can remain after rollback.
- Code rollback must ignore unknown tables/columns safely.
- Do not ship irreversible migration until tests cover old and new paths.

## Required tests

- migrations can run twice without error;
- existing config/idempotency store behavior remains green;
- new run/case tables are business-scoped;
- unique dedupe behavior prevents duplicate active cases;
- redacted artifact sample is persisted without secret patterns;
- old DB fixture can run current report path after migration.

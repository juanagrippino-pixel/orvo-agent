# Run Ledger Foundation

This is the first additive slice for Orvo Brain run/artifact history. It defines a safe ledger contract without wiring it into the current production report paths yet.

## Current slice

Implemented in:
- `app/brain/run_ledger.py`
- `app/brain/storage.py`

Core objects:
- `RunRecord`: one report/run lifecycle for a business, including safe config reference/digest fields for future operator audit views.
- `ConnectorRunOutcome`: per-connector execution result, with optional evidence lineage references.
- `ArtifactRef`: reference or summary metadata for generated artifacts; does not embed full secrets or large payloads, and can link to evidence refs / Operational Case ids.
- `DispatchOutcomeRef`: reference to a delivery/dispatch attempt, including status, idempotency key, attempt number, delivery message id, and optional provider response reference.
- `RunLedger`: protocol with create/update/list/get and append semantics.
- `InMemoryRunLedger`: test/early in-process store.
- `SQLiteRunLedger`: durable SQLite implementation using the existing storage pattern.

`init_schema(conn)` now also creates:
- `run_ledger`
- `idx_run_ledger_business_started`
- `idx_run_ledger_status_started`

## Safety rules

The ledger is for audit/operator views, not secret storage.

Metadata dictionaries are recursively redacted for secret-shaped keys including:
- `access_token`
- `refresh_token`
- `api_key` / `apikey`
- `authorization`
- `auth_header`
- `password`
- `private_key`
- `credential`
- `cookie`
- `session`
- `secret`
- `token`

Secret-shaped `error_summary` fragments such as `Bearer ...` and `api_key=...` are also redacted. This is a guardrail, not permission to store raw exception dumps.
Reference URI query params are redacted for secret-shaped keys before persistence. Store references and counts, not raw external payloads. Good examples:
- `metrics_count`
- `insights_count`
- `report_type`
- config reference + digest / compiled runtime reference
- artifact URI/reference
- evidence references and Operational Case ids
- dispatch idempotency key, attempt number, provider response reference
- delivery message id
- concise error summary

Avoid:
- OAuth tokens
- API keys
- raw connector responses
- customer PII beyond existing explicit dispatch references

## Future integration points

### Scheduled run

In `app/brain/runner.py`, around each due schedule execution:
1. `create_run(business_id=run.business_id, trigger_type="scheduled", config_ref=..., config_digest=..., summary_metadata={"schedule_id": run.schedule_id, "report_type": run.report_type})`
2. Append one `ConnectorRunOutcome` per enabled connector when connector registry/runtime policy exists. Include non-secret evidence refs when available.
3. Append an `ArtifactRef` for the generated daily report/summary and any Operational Case/evidence references it projects.
4. Append a `DispatchOutcomeRef` from `PipelineResult.dispatch`, including idempotency key, attempt number/retry context, provider response reference, and delivery message id where available.
5. `update_run(..., status="succeeded" | "failed" | "partial", finished_at=...)`.

### Forced/manual run

In forced CLI/API paths such as `scripts/run_orvo_brain_reports.py --force` and the future operator API:
1. Use `trigger_type="forced"` for operator/CLI initiated runs.
2. Include non-secret operator/request metadata only, e.g. `{"report_type": "daily", "source": "cli"}`.
3. Reuse the same append/update pattern as scheduled runs so history views can compare scheduled and forced executions.

### Dispatch

In `app/brain/dispatch.py` or a thin wrapper around `dispatch_daily_report`:
1. Map `ReportDispatchResult.status` to `DispatchOutcomeRef.status`.
2. Store `idempotency_key`, `attempt_number`, `delivery.message_id` if present, provider response reference if safe, and `error_summary` if failed.
3. Record retries as separate dispatch outcomes with increasing attempt numbers or as non-secret metadata.
4. Do not store message text in the ledger; store a report artifact ref instead if full rendering needs audit access.

## Status semantics

Runs start as `running`.
Terminal statuses are:
- `succeeded`
- `failed`
- `partial`
- `cancelled`

Once terminal, a run cannot be mutated or appended to. Terminal statuses require `finished_at`, and timestamp fields must be timezone-aware with `finished_at >= started_at`. This protects audit history from accidental rewrites while still allowing future code to read and list historical records.

`list_runs()` is intentionally bounded by default (`limit=100`) for future operator views; callers can pass a smaller limit or `None` for internal maintenance scans.

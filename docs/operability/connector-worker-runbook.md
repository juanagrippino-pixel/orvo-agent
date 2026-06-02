# Orvo Brain connector worker runbook

Status: accepted operational pattern for the current in-process worker path.

## Worker pattern

Every connector worker follows the same five-stage shape defined in
`app.brain.worker_contracts.ADAPTER_WORKER_STAGES`:

1. **validate** — compile `BusinessConfig` through the connector registry/runtime;
   fail before side effects when required params, secret refs, runtime mode or
   metric family contracts are invalid.
2. **fetch** — call only the allowlisted adapter factory declared by
   `ConnectorSpec.executor`; tenant config never controls import paths.
3. **build_report** — adapter returns a `DailyReport` with cited `Metric`
   objects. Raw secrets must not be embedded in metrics, evidence, errors or run
   metadata.
4. **emit_metrics** — emitted metric keys/families must match the connector
   registry and semantic metric registry.
5. **record_freshness** — runtime/run ledger/case projections record freshness
   and data-quality warnings for operator surfaces.

## Adapter protocol

Daily report adapters satisfy `DailyReportAdapter`: allowlisted keyword args in,
`DailyReport` out. Current adapters may keep connector-specific signatures, but
the worker boundary treats them as registry-built kwargs only.

Use `validate_daily_report_adapter()` whenever loading an adapter dynamically.
The registry does this in `ConnectorExecutorMetadata.load_factory()`.

## Merge policy

Multi-connector daily reports must use
`app.brain.report_merge_policy.merge_daily_reports` and record/know
`MERGE_POLICY_VERSION` when exposing worker metadata.

Policy v1:

- one canonical output metric per metric key;
- numeric duplicates with the same unit are summed;
- duplicate evidence is deduped by `(source, label)` preserving first-seen order;
- non-numeric duplicates or unit mismatches are deterministic last-wins;
- insights are regenerated after merge with business thresholds when available.

## Failure handling

- Connector-specific failures should be wrapped in `PipelineConnectorError` with
  `connector_type` and `connector_id` when known.
- Public/operator errors must pass through redaction helpers; never log raw
  access tokens, refresh tokens, bearer/basic credentials or canary values.
- Worker logs should include a correlation id from `AdapterWorkerContext` or the
  run ledger id once available.

## Verification checklist

Before shipping connector-worker changes:

```bash
pytest tests/test_worker_contracts.py tests/test_brain_pipeline.py tests/test_brain_runner.py -q
pytest -q
```

Keep `docs/specs/` and `GUARDRAILS.md` as contract guardrails. Stop and ask if
an endpoint envelope, adapter return shape, or metric merge behavior must change.

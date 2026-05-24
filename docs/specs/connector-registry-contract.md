# Connector Registry Contract

Status: Draft implementation contract
Date: 2026-05-24
Related: `docs/specs/compiled-runtime-contract.md`, `docs/specs/tenant-secret-redaction-contract.md`

## Purpose

The connector registry is the source of truth for external-system capabilities, required params, secret refs, health semantics, rate limits, emitted metric families, and execution modes.

Adapters translate external APIs. The registry describes how Orvo may safely use them.

## Registry entry shape

```python
class ConnectorSpec(BaseModel):
    connector_type: str
    version: str
    display_name: str
    modes: set[Literal["preview", "forced", "scheduled", "operator_triggered"]]
    required_params: list[ParamSpec]
    optional_params: list[ParamSpec]
    required_secret_refs: list[SecretRefSpec]
    capabilities: set[str]
    emitted_metric_families: set[str]
    emitted_event_families: set[str]
    health_policy: ConnectorHealthPolicy
    rate_limit_policy: ConnectorRateLimitPolicy | None = None
    executor_ref: str
    redaction_policy_ref: str
```

## Initial connector specs

### `tiendanube`

Required params:

- `store_id` or canonical business/store identifier;
- timezone/currency inherited from business config when absent.

Required secret refs:

- API access token ref.

Optional secret refs:

- app/client metadata ref if implementation needs it.

Capabilities:

- `commerce.orders.read`
- `commerce.revenue.read`
- `commerce.products.read`
- `commerce.inventory.read` when available
- `runtime.freshness.report`

Initial emitted metric families:

- `commerce.orders`
- `commerce.revenue`
- `commerce.inventory`
- `runtime.freshness`
- `runtime.data_quality`

Degraded states:

- `unauthorized`
- `rate_limited`
- `network_error`
- `malformed_response`
- `partial_inventory_unavailable`
- `stale_success`

### `google_sheets`

Modes:

- `preview`
- `forced`
- `scheduled`

Required params:

- `spreadsheet_id`
- `range_name`

Required secret refs:

- Google credentials/service account ref when the execution environment does not inject a test/fake service.

Capabilities:

- `manual.commerce_metrics.read`
- `runtime.freshness.report`

Initial emitted metric families:

- `commerce.orders`
- `commerce.revenue`
- `commerce.inventory` when columns exist
- `runtime.freshness`
- `runtime.data_quality`

Use only as manual/import source when source-of-truth connectors are unavailable.

### `csv`

Modes:

- `preview`
- `forced`
- `scheduled` only when `csv_path` is stable and policy allows it

Required params:

- `csv_path`

Optional params:

- `source_label`

Required secret refs:

- none

Capabilities:

- `local.preview.read`
- `manual.commerce_metrics.read`

Initial emitted metric families:

- `commerce.orders`
- `commerce.revenue`
- `commerce.inventory` when columns exist
- `runtime.freshness`
- `runtime.data_quality`

Scheduled mode requires stable accessible path and explicit policy.

### `meta_ads`

Post-pilot connector. It is not required for the first Tiendanube/WhatsApp pilot.

Capabilities:

- `ads.spend.read`
- `ads.delivery.read`
- `runtime.freshness.report`

Cross-source cases must suppress claims when commerce or ads source is stale.

## Health state taxonomy

| State | Meaning | Owner-facing behavior |
| --- | --- | --- |
| `ok` | Connector executed and emitted valid data. | Claims may use evidence. |
| `degraded` | Partial data or non-critical capability unavailable. | Claims must include caveat or narrow scope. |
| `stale` | Last trustworthy data too old for policy. | Suppress dependent advice; open/update `data_stale`. |
| `unauthorized` | Credential/auth issue. | Open/update `data_stale`; ask reconnect/refresh. |
| `rate_limited` | API throttled. | Retry only per policy; show caveat. |
| `failed` | Unexpected failure. | No unsupported claims; inspect ledger. |

## Source-of-truth rules

- Connector specs are compile-time inputs for `CompiledBusinessRuntime`.
- Executors may not invent emitted metrics outside registry definitions.
- Adapters may emit legacy keys only when metric registry aliases define them.
- Connector errors must be typed and redacted.
- New connectors require contract tests before owner-facing use.

## Required tests

- registry contains required specs for currently enabled connectors;
- Tiendanube spec lists expected modes, required secret refs, and emitted families;
- invalid params fail compile-time validation;
- connector failure maps to typed health state;
- raw URLs/tokens never appear in health errors;
- legacy adapter execution remains compatible through registry wrapper.

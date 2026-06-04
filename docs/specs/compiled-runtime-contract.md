# Compiled Runtime Contract

Status: Draft implementation contract
Date: 2026-05-24
Related: `docs/architecture/phase-a-control-plane-contract.md`, `docs/roadmap/d2c-control-plane-roadmap.md`

## Purpose

`CompiledBusinessRuntime` is the immutable executable plan for preview, forced, scheduled, and operator-triggered Orvo runs. It is the boundary between control-plane configuration and runtime/data-plane execution.

The first implementation may wrap existing pipeline functions, but every new runtime path must move toward this contract instead of creating a parallel shortcut.

## Non-negotiable rules

1. Runtime execution consumes a compiled plan; it does not silently rewrite business config, schedules, connector definitions, thresholds, templates, or secret refs.
2. Preview, forced, and scheduled paths must converge on the same compile/execute function or an explicitly tested compatibility shim.
3. Compiled runtimes carry secret references only, never raw secret values.
4. The compiled plan must be serializable for inspection after redaction.
5. The compiled plan must be hashable so a run ledger can explain which runtime version executed.
6. Tiendanube/WhatsApp-first work must still go through this contract.

## Conceptual model

```python
class CompiledBusinessRuntime(BaseModel):
    runtime_id: str
    business_id: str
    business_name: str
    tenant_id: str | None = None
    timezone: str
    currency: str
    run_mode: Literal["preview", "forced", "scheduled", "operator_triggered"]
    report_date: date
    compiled_at: datetime
    compiled_from_hash: str
    connector_refs: list[CompiledConnectorRef]
    metric_policy: CompiledMetricPolicy
    case_policy: CompiledCasePolicy
    delivery_policy: CompiledDeliveryPolicy
    artifact_policy: CompiledArtifactPolicy
    redaction_policy: CompiledRedactionPolicy
    feature_flags: dict[str, bool]
```

## Compile inputs

Allowed inputs:

- `BusinessConfig`
- `ReportSchedule` where relevant
- operator override request, if audited and tenant-scoped
- connector registry definitions
- metric registry definitions
- case/action policies
- delivery policy
- secret refs from configuration
- runtime defaults and version

Forbidden inputs:

- raw environment values in compiled artifacts
- ad-hoc request parameters that are not validated
- LLM-generated thresholds/policies
- connector-specific magic embedded in report templates

## Compile outputs

Minimum output fields:

| Field | Purpose |
| --- | --- |
| `runtime_id` | Stable unique id for this compiled plan. |
| `compiled_from_hash` | Hash of relevant config/registry/policy inputs. |
| `connector_refs` | Ordered connector executions with registry version and secret refs. |
| `metric_policy` | Registered metric aliases and validation mode. |
| `case_policy` | Enabled case families and thresholds. |
| `delivery_policy` | WhatsApp/report dispatch rules and idempotency key shape. |
| `artifact_policy` | What to persist, redact, and expose. |
| `redaction_policy` | Secret/PII sanitization behavior. |

## Execution lifecycle

```text
compile request
  -> validate config/registry/secret refs
  -> produce CompiledBusinessRuntime
  -> record run start in run ledger
  -> execute connector refs
  -> emit normalized metrics/evidence/degraded states
  -> validate metric registry
  -> run deterministic detections/case engine
  -> render projections/dispatch if policy allows
  -> record run end and artifacts
```

## Compatibility shim

The first implementation can call existing functions such as current pipeline/report builders internally. The shim must still:

- assign a `run_id`;
- record compiled runtime metadata;
- call connector executors through registry wrappers where possible;
- capture connector status/degraded state;
- preserve existing `DailyReport` output behavior;
- pass existing runtime docs/examples tests.

## Acceptance tests

Required tests before this is considered implemented:

- compiling the same config twice yields the same `compiled_from_hash` when inputs are unchanged;
- raw secret values are absent from runtime serialization;
- preview, forced, and scheduled paths share the same compiler or tested shim;
- invalid connector config fails at compile time, not halfway through dispatch;
- runtime execution cannot mutate business config silently;
- existing Hito0/report tests remain green.

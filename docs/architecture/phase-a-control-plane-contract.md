# Phase A Control Plane Architecture Contract

Status: Proposed
Date: 2026-05-24
Source plan: `docs/plans/2026-05-24-orvo-control-plane-program.md`
Related ADRs:

- `docs/adr/0001-control-plane-bounded-contexts-and-module-ownership.md`
- `docs/adr/0002-operational-case-native-issue-object.md`
- `docs/adr/0003-deterministic-detection-llm-explanation-boundary.md`
- `docs/adr/0004-autonomous-operating-toolchain.md`

## Purpose

This document is the architectural contract for the Phase A Orvo Control Plane pivot. It is deliberately implementation-facing: future workers should use it to decide where code belongs, which dependencies are legal, what must remain compatible with Hito0, and what invariants cannot be broken.

The pivot is additive first. The current Orvo Brain report path stays operational while the platform layer is introduced around it.

## Applied Atlassian-style platform principles

Phase A must copy Atlassian's structural primitives, not its surface complexity. The required interpretation for Orvo is:

1. Build a platform/control plane, not a pile of scripts: new modules expose stable contracts and contract/invariant tests before other workers depend on them.
2. Separate control plane from runtime/data plane: configuration, policies, schedules, permissions, templates, and validated runtime specs are compiled before execution; connector pulls, detections, dispatch, and automations execute from that compiled contract.
3. Use a native issue object: `OperationalCase` is Orvo's Jira-style issue object; reports, alerts, timelines, queues, and automations are projections/actions around cases.
4. Keep the core deterministic: metrics, thresholds, detections, case creation, priority, lifecycle transitions, degraded-mode decisions, and dispatch idempotency are reproducible and auditable; LLMs may only explain/project validated facts.
5. Centralize edge/gateway concerns: auth, rate limits, structured logging, routing, tenant isolation, permission scopes, audit logging, observability, and idempotency belong in shared platform layers, not scattered through adapters or report renderers.
6. Make integrations registry/plugin-like: connector metadata, capabilities, required fields, secret refs, limits, health semantics, and executors are discoverable through a typed registry.
7. Treat operability as product: every run must be explainable through ledgers, artifacts, health/degraded state, replay hooks, and sanitized audit events.
8. Keep surfaces lightweight: WhatsApp and the operator API are initial interfaces; they must not become hidden sources of product truth.
9. Prefer additive maintenance paths: schemas/contracts are versioned or compatibility-shimmed, migrations preserve Hito0 behavior, and broad rewrites are forbidden until tests prove replacement parity.


## Operating/toolchain alignment

The autonomous organization that builds this platform must follow the same control-plane principles as the product:

- product work is represented as durable task packets/manifests, not transient chat state;
- implementation happens through external worktrees and reviewable commits;
- cross-boundary changes require ADR/spec/contract updates;
- cron-run workers must not recursively create or mutate cron jobs;
- Vasilios/Atlassian-inspired broker/control-plane/gateway/observability patterns are translated into Orvo gradually through `docs/organization/orvo-operating-toolchain-blueprint.md`, `docs/architecture/vasilios-atlassian-platform-patterns.md`, and `docs/specs/worker-handoff-manifest.md`.

## Control plane vs runtime/data plane boundary

The platform split is a hard architecture boundary for future workers.

### Control plane owns

- business and tenant context
- connector configuration and secret references
- schedules and run policies
- metric/case/report policies and thresholds
- permissions, auth policy, tenant isolation, and operator API contracts
- templates and allowed surface actions
- compiled runtime specs and their version/hash metadata

### Runtime/data plane owns

- connector execution against external systems
- source freshness and degraded-mode observations
- normalized metric/evidence emission
- deterministic detection and case candidate generation
- case engine execution against stored state
- report/queue/timeline projection rendering
- dispatch/action execution and idempotency checks
- run ledger, artifact, and audit-event writes

### Boundary rule

Runtime workers execute an already validated `CompiledBusinessRuntime`. They may record observed outcomes and typed failures, but they must not silently rewrite tenant configuration, thresholds, permissions, schedules, templates, or connector definitions during execution. Control-plane workers may change config/policy only through explicit operator/API flows that are tenant-scoped and audited.

## Current repo baseline to preserve

Do not treat the repo as blank. Current behavior is grounded in these paths:

| Capability | Current path(s) | Compatibility rule |
| --- | --- | --- |
| Core report data models | `app/brain/models.py` | Preserve `Evidence`, `Metric`, `Insight`, `InsightThresholds`, and `DailyReport` semantics. Do not convert to dataclasses. |
| Business config and schedules | `app/brain/config.py` | Preserve `BusinessConfig`, `ConnectorConfig`, `ReportSchedule`, JSON helpers, and store interface expectations. |
| SQLite config/idempotency store | `app/brain/storage.py` | Add tables idempotently; do not break existing table names or store methods. |
| Adapters | `app/brain/adapters/*.py` | Keep external translation thin; move cross-connector policy to registry/runtime modules. |
| Insight generation | `app/brain/insights.py` | Keep deterministic and evidence-backed. No LLM detection. |
| Report composition | `app/brain/reporting.py` | Keep deterministic owner-facing renderer during Phase A. |
| Dispatch | `app/brain/dispatch.py`, `app/brain/delivery.py` | Preserve idempotent daily send path. Add ledger/outbox later without removing current behavior. |
| Scheduled execution | `app/brain/runner.py`, `app/brain/scheduler.py` | Preserve due-schedule semantics and multi-connector scheduled path. |
| Forced execution | `scripts/run_orvo_brain_reports.py` | Preserve CLI contract while migrating toward compiled runtime parity. |
| HTTP previews | `server.py` | Preserve existing `/brain/reports/daily*` endpoints while adding operator API separately. |
| Runtime docs/examples | `docs/orvo-brain-runtime.md`, `examples/*`, `tests/test_runtime_docs_examples.py` | Keep examples valid and secrets redacted. |

## Phase A dependency map

Phase A introduces five tightly related platform pieces. They must be built in this dependency order so workers do not create competing abstractions.

```text
Control plane state: BusinessConfig + schedules + policies + permissions + operator inputs
  -> validated CompiledBusinessRuntime
      -> Connector registry
          -> Connector executions
              -> Metric registry validation
                  -> deterministic detections
                      -> Operational Case engine
                          -> projections / dispatch
      -> Run ledger records every step
```

The arrows above are one-way for a run: runtime/data-plane execution records facts and failures back to ledgers/audit surfaces, but it does not mutate the control-plane source of truth except through explicit case/action state transitions owned by their contexts.


## Platform broker extension

The video-derived platform shape adds one Phase A extension: config-changing requests should move toward a broker/status pattern before Orvo adds many operator endpoints.

```text
Operator/API request
  -> Broker command
  -> BrokerOperation
  -> ProvisioningJob
  -> Worker side effects
  -> Control-plane state/artifacts
  -> Runtime compilation
  -> OperationStatus
```

Initial broker commands:

- create/update/deactivate business workspace;
- create/update/deactivate connector instance;
- create/update workflow scheme;
- create/update SLA policy;
- create/update automation rule;
- create/update surface projection;
- compile runtime preview;
- inspect operation status.

The broker must be idempotent, tenant-scoped, audited, and safe to retry. The first implementation can be a service-layer contract plus SQLite-backed operation/status tables; external queues or a full Open Service Broker implementation are non-goals until scale or ecosystem compatibility requires them.

Proposed future modules, when implementation reaches this slice:

```text
app/brain/platform/
  __init__.py
  broker.py              # broker command handlers
  catalog.py             # service/plan catalog
  operations.py          # BrokerOperation models/status
  provisioning_queue.py  # DB-backed queue/outbox abstraction
  provisioning_worker.py # worker execution loop/contracts
```

Suggested future tests:

```text
tests/contracts/
  test_platform_broker_contract.py
  test_provisioning_queue_contract.py

tests/invariants/
  test_broker_idempotency.py
  test_operation_status_is_auditable.py
  test_provisioning_worker_does_not_mutate_runtime_without_operation.py
```

### 1. Compiled runtime

Proposed owner: Runtime & Orchestration (ADR-0001 C1)

Proposed modules:

- `app/brain/runtime/compiled.py`
- `app/brain/runtime/compiler.py`
- `app/brain/runtime/execution.py`

Contract:

- `CompiledBusinessRuntime` is the single executable plan for preview, forced run, and scheduled run.
- It is compiled from `BusinessConfig`, `ReportSchedule` where relevant, operator overrides, connector registry definitions, metric registry definitions, and secret references.
- It contains only references to secrets, not raw secret values in artifacts/logs.
- It normalizes thresholds and connector execution policy before a run starts.
- It makes current forced/scheduled divergence impossible over time; the CLI and scheduler should both call the same execution function.

Initial conceptual fields:

- `runtime_id`
- `business_id`
- `business_name`
- `timezone`
- `currency`
- `run_mode`: `preview`, `forced`, `scheduled`
- `report_date`
- `enabled_connector_refs`
- `thresholds`
- `delivery_policy`
- `case_policy`
- `artifact_policy`
- `secret_refs`
- `compiled_at`
- `compiled_from_hash`

Compatibility shim:

- The first implementation may call existing functions in `app/brain/pipeline.py` internally.
- Do not remove current pipeline functions until tests prove preview, forced, and scheduled runtime parity.

### 2. Connector registry

Proposed owner: Connectors & Ingestion (ADR-0001 C2)

Proposed modules:

- `app/brain/connectors/contracts.py`
- `app/brain/connectors/registry.py`
- `app/brain/connectors/policies.py`

Contract:

- A connector registry entry defines `connector_type`, required params, required secret refs, capabilities, executor, optional validation hooks, and runtime policy defaults.
- Current scattered connector-type selection in `app/brain/pipeline.py`, `app/brain/runner.py`, and `scripts/run_orvo_brain_reports.py` must be migrated behind this registry.
- Existing adapters under `app/brain/adapters/` remain implementation details behind registry executors.
- Registry validation runs at compile time so a bad connector config fails before partial execution.

Initial capability examples:

- `google_sheets`: emits commerce/manual metrics; supports preview and scheduled execution.
- `csv`: emits commerce/manual metrics; supports local preview and scheduled execution only when path is accessible.
- `tiendanube`: emits commerce/order/inventory metrics; requires commerce credentials; stock can be optional/degraded.
- `mercadolibre`: emits marketplace commerce metrics; requires marketplace credentials.
- `meta_ads`: emits ad delivery/spend metrics; secondary context for commerce reports.

Compatibility shim:

- Registry executors can initially wrap `build_daily_report_from_*` adapter functions.
- Keep adapter tests intact while adding registry contract tests.

### 3. Run ledger

Proposed owner: Runtime & Orchestration for writes; Trust, Security & Observability for policy (ADR-0001 C1/C6)

Proposed modules:

- `app/brain/runtime/ledger.py`
- `app/brain/audit/events.py`

Contract:

- Every preview/forced/scheduled run gets a `run_id`.
- The ledger records run start/end, connector executions, artifacts, dispatch attempts, errors, degraded-mode decisions, and evidence lineage references.
- Ledger records are safe for operator inspection and must not contain raw access tokens, OAuth refresh tokens, WhatsApp tokens, service-account private keys, or full unredacted request URLs with token query params.
- Ledger artifacts should be enough to answer: what ran, which connectors succeeded/failed/degraded, what metrics were emitted, what cases were opened/updated, and whether delivery was accepted/skipped/failed.

Initial table concepts, added idempotently to `app/brain/storage.py` or a storage extension:

- `brain_runs`
- `brain_connector_runs`
- `brain_artifacts`
- `brain_dispatch_attempts`
- `brain_run_events`

Compatibility shim:

- Current `idempotency_keys` remains the duplicate-send gate until dispatch attempts/outbox behavior is explicitly implemented and tested.

### 4. Metric registry

Proposed owner: Semantics & Insights (ADR-0001 C3)

Proposed modules:

- `app/brain/semantics/metric_registry.py`
- `app/brain/semantics/evidence.py`

Contract:

- Every metric key used for insight/report/case behavior must have a registry definition.
- Registry definitions include key, label, unit, family, namespace/channel rules, allowed evidence sources, aggregation semantics, report participation, case participation, and deprecation status.
- Adapters may emit legacy keys during migration, but any new detection/case rule must read through registered semantics.
- Registry validation catches current-class issues such as Tiendanube emitting generic `revenue_today` while downstream ad/report logic expects namespaced Tiendanube revenue keys.

Initial metric families:

- `commerce.orders`
- `commerce.revenue`
- `commerce.inventory`
- `commerce.fulfillment`
- `ads.spend`
- `ads.delivery`
- `ads.roas`
- `support.conversations`
- `runtime.freshness`
- `runtime.data_quality`

Compatibility shim:

- Preserve current `Metric.key` strings and add registry aliases/deprecation metadata rather than renaming all metrics at once.

### 5. Operational Case engine

Proposed owner: Cases & Workflow (ADR-0001 C4, ADR-0002)

Proposed modules:

- `app/brain/cases/models.py`
- `app/brain/cases/engine.py`
- `app/brain/cases/storage.py`
- `app/brain/cases/projections.py`

Contract:

- `OperationalCase` is the native issue object for Orvo. An insight/report/alert can point at a case or project case state, but it must not become a parallel workflow object.
- Case creation consumes deterministic detections and runtime/data-health events.
- Case dedupe is stable for the same business, case type, entity scope, primary metric, and time grain.
- Case lifecycle transitions are append-only and auditable.
- Case priority is deterministic and explainable.
- Existing `Insight` and `DailyReport` flows remain valid while cases are introduced; initial case projection can run in parallel before owner-facing reports switch to cases.

Native issue object rule:

- One business-worthy unit of attention equals one `OperationalCase` lineage, not one WhatsApp paragraph, one insight row, or one automation run.
- Reports, queues, timelines, messages, and automations must reference `case_id`/evidence/action records once the case engine exists.
- Worker-created alternatives such as `Alert`, `Task`, `Opportunity`, or `Incident` may only be projections/subtypes backed by `OperationalCase`, not independent lifecycle stores.

Compatibility shim:

- First case implementation may create cases from current `Insight` objects emitted by `app/brain/insights.py` without changing `DailyReport` shape.

## Proposed repo/module structure

The structure below is the target additive scaffold for Phase A. Workers should create packages only when needed by their task, but should not invent competing locations.

```text
app/brain/
  adapters/                 # existing external source adapters; keep thin
  connectors/
    __init__.py
    contracts.py            # ConnectorDefinition, ConnectorExecutionResult, capability types
    registry.py             # built-in registry for csv/google_sheets/tn/ml/meta_ads
    policies.py             # timeout/retry/freshness/degraded policy primitives
  runtime/
    __init__.py
    compiled.py             # CompiledBusinessRuntime and nested config models
    compiler.py             # BusinessConfig + registry -> compiled runtime
    execution.py            # preview/forced/scheduled execution against compiled runtime
    ledger.py               # run ledger interfaces and SQLite implementation
  semantics/
    __init__.py
    metric_registry.py      # MetricDefinition registry and validation
    evidence.py             # evidence normalization / lineage helpers
    detections.py           # optional extraction from current insights over time
  cases/
    __init__.py
    models.py               # OperationalCase, CaseEvidence, CaseTransition, CaseComment, CaseAction
    engine.py               # deterministic create/update/dedupe/reopen logic
    storage.py              # case store interface + SQLite implementation
    projections.py          # open queue, timeline, report projection helpers
  projections/
    __init__.py
    reports.py              # case-native report projection once ready
    case_queue.py           # operator queue read models
  operator_api/
    __init__.py
    routes.py               # internal config/compile/history/cases endpoints; auth/routing/tenant scope enforced at edge
  security/
    __init__.py
    secrets.py              # secret refs and resolution boundary
    gateway.py              # shared auth, rate limit, tenant isolation, permission/idempotency helpers when needed
  audit/
    __init__.py
    events.py               # audit/run event shapes and redaction helpers
```

Test structure:

```text
tests/contracts/
  test_compiled_runtime_contract.py
  test_connector_registry_contract.py
  test_metric_registry_contract.py
  test_case_engine_contract.py

tests/invariants/
  test_no_uncited_metrics.py
  test_preview_forced_scheduled_parity.py
  test_case_dedupe_idempotency.py
  test_secret_redaction.py
  test_llm_boundary.py
```

Contract/docs structure:

```text
contracts/
  brain-runtime.schema.json       # optional once schemas stabilize
  connector-definition.schema.json
  operational-case.schema.json

docs/specs/
  compiled-runtime.md
  connector-registry.md
  run-ledger.md
  metric-registry.md
  operational-cases.md
```

Do not create empty placeholder packages just to match this tree. Create them when they carry tests, contracts, or implementation.

## Migration strategy

### Stage 0: Documentation and invariants

- Land ADRs and this contract.
- Add `docs/adr/`, `docs/architecture/`, and later `docs/specs/` only as needed.
- No runtime behavior change.

### Stage 1: Registry and compiled runtime scaffold

- Add connector registry definitions that wrap existing adapter functions.
- Add `CompiledBusinessRuntime` that can represent current `BusinessConfig` + selected connectors + thresholds.
- Add tests proving compilation fails early for missing required params.
- Keep existing `app/brain/pipeline.py` public functions.

### Stage 2: Forced/scheduled/preview parity

- Route `scripts/run_orvo_brain_reports.py --force`, scheduled runner, and HTTP/operator preview through the same compiled execution path.
- Preserve the current CLI output shape unless tests explicitly migrate it.
- Add parity tests for same business/date/input.

### Stage 3: Run ledger

- Add idempotent SQLite tables for run/connector/artifact/dispatch records.
- Write ledger rows from compiled execution.
- Keep `idempotency_keys` unchanged as the duplicate-send gate until outbox semantics exist.

### Stage 4: Metric registry

- Introduce registered metric definitions and aliases for current keys.
- Validate connector outputs against registry in warning/test mode first.
- Migrate insights/reporting to registry lookups gradually.

### Stage 5: Case engine parallel path

- Add case models/storage/engine.
- Generate cases from current deterministic insights in parallel with current `DailyReport` output.
- Add queue/timeline projections.
- Switch owner-facing report source to case projection only after tests prove compatibility and usefulness.

## Non-breaking Hito0 rules

1. Existing tests must keep passing while Phase A scaffolds land.
2. Do not remove or rename existing modules, functions, endpoints, scripts, or example files without a migration PR and compatibility tests.
3. Do not broaden the rewrite. Wrap first, extract second, delete only after green tests and explicit deprecation.
4. Do not block the current WhatsApp daily report path on a new case engine until case projections are tested.
5. Do not make external credentials required for tests that currently run locally with fakes/placeholders.
6. Do not commit real tokens or client secrets. Docs/examples use `[REDACTED]`, `tn_test_token`, or similar placeholders.

## Explicit invariants future workers must preserve

### Data/evidence invariants

- Every `Metric` used in report, detection, or case logic must have at least one `Evidence` item.
- Every owner-facing number must trace to a metric, case evidence, or ledger artifact.
- Metric key semantics must be registered before new case/detection/report logic depends on them.
- Source freshness/degraded state must be explicit; missing data cannot be silently treated as zero unless the registry says zero is a valid observed value.

### Runtime invariants

- Preview, forced, and scheduled execution must compile the same business config into the same connector plan for the same inputs.
- Connector execution order must be deterministic.
- One failed secondary connector must not corrupt successful primary connector artifacts.
- Run ledger writes must be idempotent or safely retryable.
- Dispatch idempotency must stay business/date/report-type scoped until superseded by tested outbox semantics.
- Runtime/data-plane execution must not mutate control-plane configuration, schedules, permissions, templates, or registry definitions except through explicit audited operator/API commands.

### Case invariants

- A case cannot exist without evidence.
- Case creation, dedupe, priority, and lifecycle transition rules must be deterministic.
- Transitions are append-only.
- Reopening a case preserves prior resolution history.
- Reports/alerts are projections of case/report state and do not become hidden workflow state.

### LLM boundary invariants

- LLMs may explain but not calculate, detect, create cases, prioritize cases, mutate lifecycle, decide degraded mode, or decide dispatch.
- LLM-generated text must be validated against allowed facts/actions before customer-facing use.
- Unsupported LLM claims are suppressed, not trusted.

### Security/observability invariants

- Secret values are resolved at execution time and never stored in compiled runtime artifacts, run ledger rows, docs, or tests.
- Errors stored in the ledger are sanitized.
- Operator APIs must be internal by default and tenant-scoped before exposing live data.
- Artifact retention must favor replay/debuggability without raw secret-bearing payloads.
- Gateway/edge paths must enforce auth, tenant isolation, permission scopes, rate limits, routing rules, structured logging, audit logging, observability, and idempotency before they trigger runtime/data-plane work.
- WhatsApp, HTTP previews, operator API endpoints, and future UI routes are surfaces over the same contracts; none may bypass compiled runtime, case, audit, or idempotency rules for convenience.

## Worker ownership guidance

- Compiled runtime workers should touch `app/brain/runtime/*`, tests under `tests/contracts/`, and only minimal adapters in `pipeline.py`/runner/script wrappers.
- Connector registry workers should touch `app/brain/connectors/*`, adapter wrapper tests, and registry contract tests.
- Run ledger workers should touch `app/brain/runtime/ledger.py`, storage schema additions, and invariant tests for redaction/idempotency.
- Metric registry workers should touch `app/brain/semantics/*`, insights/reporting consumers only through compatibility aliases, and no adapter rewrites unless needed by tests.
- Case engine workers should touch `app/brain/cases/*`, case storage/projection tests, and avoid changing WhatsApp reporting until projection tests exist.
- Operator API workers should add new internal endpoints rather than changing existing public preview endpoint behavior.

## Acceptance criteria for Phase A completion

Phase A is complete when the repo has:

1. ADRs and this architecture contract committed.
2. A tested `CompiledBusinessRuntime` used by preview, forced, and scheduled paths.
3. A typed connector registry covering current connector types.
4. A durable run ledger with sanitized run, connector, artifact, dispatch, and error records.
5. A metric registry covering current report/insight metric keys and aliases.
6. First Operational Case models/storage/engine behind tests, even if owner-facing reports still render current `DailyReport` initially.
7. Contract/invariant tests for preview/forced/scheduled parity, evidence coverage, secret redaction, case dedupe, and LLM boundary.
8. Existing Hito0 tests still green.

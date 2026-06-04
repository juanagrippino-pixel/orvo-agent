# ADR-0001: Control Plane bounded contexts and module ownership

Status: Proposed
Date: 2026-05-24

## Context

The program plan in `docs/plans/2026-05-24-orvo-control-plane-program.md` pivots Orvo from a deterministic WhatsApp reporting path into an Atlassian-style operational control plane.

The current repository already has the nucleus that must be preserved:

- Core evidence, metric, insight, threshold, and report models live in `app/brain/models.py`.
- Business and schedule configuration live in `app/brain/config.py`.
- SQLite config and idempotency storage live in `app/brain/storage.py`.
- Current adapters live under `app/brain/adapters/` for sample, CSV, Google Sheets, Tiendanube, MercadoLibre, and Meta Ads.
- Current report execution is split between `app/brain/pipeline.py`, `app/brain/runner.py`, `app/brain/scheduler.py`, and `scripts/run_orvo_brain_reports.py`.
- Current owner-facing projections and transport live in `app/brain/reporting.py`, `app/brain/dispatch.py`, `app/brain/delivery.py`, and preview endpoints in `server.py`.
- Current tests cover these flows under `tests/test_brain_*.py`, `tests/test_server_brain_*.py`, and `tests/test_run_orvo_brain_reports_script.py`.

The current design works for Hito0 reporting, but the control-plane pivot needs clearer ownership boundaries before multiple workers add compiled runtime, connector registry, run ledger, metric registry, and case engine code.

## Decision

Use six bounded contexts as the architectural ownership map for Phase A and later work. Context ownership is about decision authority and dependency direction, not necessarily one Python package per context on day one.

The bounded contexts implement a control-plane/runtime-plane split:

- The control plane owns tenant/business context, connector configuration, secret references, schedules, permissions, policies, thresholds, templates, and compiled runtime specs.
- The runtime/data plane owns connector pulls, normalized metrics/evidence, deterministic detections, case engine execution, projections, dispatch/actions, run artifacts, and ledger/audit writes.
- A run executes from an already validated `CompiledBusinessRuntime`; runtime code may record outcomes and typed failures, but it must not silently mutate control-plane source-of-truth configuration or policy.

### C1. Runtime & Orchestration

Owns execution planning, compiled runtime, scheduler/forced/preview parity, run ledger writes, and top-level orchestration.

Current repo paths:

- `app/brain/pipeline.py`
- `app/brain/runner.py`
- `app/brain/scheduler.py`
- `scripts/run_orvo_brain_reports.py`

Phase A additions:

- `app/brain/runtime/compiled.py`
- `app/brain/runtime/compiler.py`
- `app/brain/runtime/execution.py`
- `app/brain/runtime/ledger.py`

C1 is the only context allowed to coordinate all others during a run.

### C2. Connectors & Ingestion

Owns adapter contracts, connector capabilities, connector runtime policies, and source-specific normalization from external systems into canonical metrics/records.

Current repo paths:

- `app/brain/adapters/google_sheets.py`
- `app/brain/adapters/csv_file.py`
- `app/brain/adapters/tiendanube.py`
- `app/brain/adapters/mercadolibre.py`
- `app/brain/adapters/meta_ads.py`
- `app/brain/adapters/sample.py`

Phase A additions:

- `app/brain/connectors/contracts.py`
- `app/brain/connectors/registry.py`
- `app/brain/connectors/policies.py`

C2 must keep adapters thin. Retries, timeouts, rate limits, auth failure classification, freshness, and degraded semantics belong in connector policy/runtime code, not scattered through report composition.

### C3. Semantics & Insights

Owns canonical metric definitions, metric families, evidence requirements, deterministic detection rules, and detection-to-case candidate contracts.

Current repo paths:

- `app/brain/models.py` for `Evidence`, `Metric`, `Insight`, `InsightThresholds`, `DailyReport`
- `app/brain/insights.py`
- `docs/insight-engine/v1-design.md`

Phase A additions:

- `app/brain/semantics/metric_registry.py`
- `app/brain/semantics/evidence.py`
- `app/brain/semantics/detections.py`

C3 owns whether a metric key means what it says. Downstream contexts must not invent ad hoc metric keys without registry entry and evidence rules.

### C4. Cases & Workflow

Owns Operational Case identity, lifecycle, dedupe, priority, assignment, transitions, comments, actions, reopen rules, and case storage contracts.

Current repo paths:

- No first-class case module exists yet.
- Current `Insight` objects in `app/brain/models.py` are findings, not workflow state.

Phase A/B additions:

- `app/brain/cases/models.py`
- `app/brain/cases/engine.py`
- `app/brain/cases/storage.py`
- `app/brain/cases/projections.py`

C4 becomes the native issue/workflow object owner. Reports and alerts are projections around cases, not replacements for cases.

### C5. Delivery & Surfaces

Owns output projections, WhatsApp report text, queue/timeline read models, internal operator API surfaces, and user-visible formatting.

Current repo paths:

- `app/brain/reporting.py`
- `app/brain/dispatch.py`
- `app/brain/delivery.py`
- `server.py` preview endpoints such as `/brain/reports/daily`, `/brain/reports/daily/csv`, `/brain/reports/daily/tiendanube`, `/brain/reports/daily/mercadolibre`, and `/brain/reports/daily/meta-ads`

Phase A additions:

- `app/brain/projections/reports.py`
- `app/brain/projections/case_queue.py`
- `app/brain/operator_api/routes.py`

C5 may render, summarize, and route. It may not decide business truth or mutate case lifecycle without going through C4 contracts.

C5 gateway/edge concerns must be explicit in every new surface: auth handoff, route ownership, tenant scoping, permission checks, rate limits, structured request logging, audit event emission, dispatch/action idempotency, and observability hooks. WhatsApp, HTTP preview endpoints, operator API endpoints, and future UI routes are edges over the same platform contracts, not separate product cores.

### C6. Trust, Security & Observability

Owns tenant boundaries, secret references, audit trail, run/artifact retention policy, permissions, replay support, and redaction rules.

Current repo paths:

- `app/brain/storage.py` for SQLite config and idempotency tables
- `app/brain/runtime_env.py` for environment readiness checks
- `docs/connectors/depth-audit.md` for current robustness and observability gaps
- `docs/operability/worktree-hygiene.md` for autonomous work hygiene

Phase A additions:

- `app/brain/security/secrets.py`
- `app/brain/audit/events.py`
- `app/brain/runtime/ledger.py` shared with C1 but policy-owned by C6

C6 owns the rule that secrets are references in runtime contracts, not inline values copied through logs, artifacts, or reports.

## Dependency direction

Allowed Phase A dependency direction:

```text
Delivery & Surfaces
  -> Cases & Workflow
  -> Semantics & Insights
  -> Connectors & Ingestion

Runtime & Orchestration coordinates all contexts.
Trust, Security & Observability supplies cross-cutting policy and storage/audit primitives.
```

More concretely:

- C1 may call C2, C3, C4, C5, and C6.
- C2 may emit canonical records/metrics and connector execution metadata, but must not call report formatting or case transition code.
- C3 may read metric registry definitions and emit deterministic findings/case candidates, but must not dispatch messages.
- C4 may consume deterministic findings/case candidates and persist workflow state, but must not fetch connector data.
- C5 may consume reports/cases/projections and call delivery transports, but must not calculate metrics.
- C5/C6 must centralize gateway concerns for surfaces: auth, rate limits, route ownership, structured logging, tenant isolation, audit logging, observability, and idempotency.
- C6 may wrap storage/audit/secret behavior, but must not embed product-specific detection rules.

## Consequences

### Positive

- Multiple workers can add Phase A scaffolds without colliding in the same files.
- Hito0 reporting remains intact while new modules wrap existing code.
- Decisions about metrics, case lifecycle, and delivery formatting stop drifting across adapter and report files.
- The future operator API gets stable module ownership before endpoints multiply.

### Negative / costs

- There will be temporary wrappers around existing `app/brain/pipeline.py` and `scripts/run_orvo_brain_reports.py` until compiled runtime fully owns preview/forced/scheduled parity.
- Some current files, especially `app/brain/pipeline.py`, currently mix C1 and C2 concerns and need incremental extraction rather than a broad rewrite.
- Workers must respect context boundaries even when one-file shortcuts would be faster.

## Invariants for future workers

1. Do not move or rewrite `app/brain/models.py` wholesale. It is a stable compatibility surface for current tests.
2. Do not remove current preview endpoints or scheduled/forced report paths while introducing compiled runtime.
3. Do not add connector-specific branching in `app/brain/runner.py` or `scripts/run_orvo_brain_reports.py`; new connector selection belongs in the connector registry and compiled runtime.
4. Do not let delivery/reporting code calculate unregistered business metrics.
5. Do not let adapters dispatch messages or transition cases.
6. Do not store secrets in run artifacts, ledger rows, docs examples, or tests.
7. Every new context boundary must include a contract test or invariant test before it becomes a dependency for another worker.
8. Every new edge/surface must document auth, tenant isolation, rate limit, routing, logging/audit, observability, and idempotency behavior before live use.
9. Runtime/data-plane code must not mutate control-plane config, permissions, policies, schedules, templates, or registry definitions during a run.

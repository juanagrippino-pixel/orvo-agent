# Vasilios/Atlassian platform patterns for Orvo

Status: Research synthesis
Date: 2026-05-24

## Evidence and caveat

This note is grounded in public repos/pages available during the 2026-05-24 audit:

- `https://cetanu.github.io/` — public site for Vasilios Syrakis.
- `https://github.com/cetanu/sovereign` — README: “JSON control-plane for Lyft's Envoy proxy,” supplying downstream Envoy proxies with dynamic configuration; templates for clusters/routes/listeners/secrets; data sources; Python plugin extension points; support points to an Atlassian email and Atlassian developer docs.
- `https://github.com/cetanu/steward` — README: implementation of the Lyft Rate-Limit service; config via HTTP/file; gRPC server; Redis; Rust; Tavern HTTP integration tests.
- `https://github.com/cetanu/envoy-formula` — SaltStack formula repository for Envoy-related configuration.
- `https://github.com/gufranco/regnant` — third-party reproduction that claims to model Vasilios's public Atlassian platform walkthrough; useful as an interpreted map, not primary authority.
- `docs/research/2026-05-24-atlassian-platform-video-analysis.md` — local analysis of the Drive video transcript: a first-person retrospective describing an Open Service Broker-style provisioning app, Sovereign/Envoy dynamic control plane, CloudFormation/Packer/SaltStack proxy infrastructure, gateway sidecars, and maintenance lessons.

Use this as platform pattern input, not as a claim that every listed component is currently or officially used inside Atlassian. Video-derived details should be cited as a personal retrospective unless independently corroborated by public repos/docs.

## Core pattern

The platform shape is:

```text
Developer / operator self-service
        ↓
Open Service Broker-style API
        ↓
Queue / worker / durable state
        ↓
Artifact/config store
        ↓
Control plane renders validated runtime config
        ↓
Gateway/data plane enforces routing/auth/rate-limit/logging
        ↓
Backends/products/connectors
        ↓
Observability + audit + SLOs + provenance
```

The important idea is not Envoy itself. The important idea is that teams do not hand-edit runtime behavior. They request capabilities through a broker/control plane; the system validates inputs, renders artifacts, applies them through a narrow data-plane boundary, and records what happened.

## Video-derived refinements

The analyzed retrospective adds concrete sequencing that should shape Orvo without forcing premature infrastructure:

1. The broker is not merely an API facade. It exposes a catalog of service plans, accepts provision/update/delete/bind-style operations, records durable operation status, and lets clients poll or inspect results.
2. The request path does not perform heavy provisioning directly. It validates intent, creates an operation/job record, and lets a worker perform side effects.
3. The control plane renders runtime behavior from templates plus context/data sources; bad product-level parameters fail before runtime config is emitted.
4. The data plane is long-lived and receives dynamic config; users do not hand-edit runtime behavior directly.
5. Cross-cutting concerns are centralized early in the request chain: auth, authorization, DDoS/rate protection, rate limiting, access logs, routing, structured logs, and observability.
6. Sidecars/extensions carry specialized logic and can receive their own dynamic config; Orvo should begin with typed plugin contracts and certification tests, not separate processes.
7. Reproducible runtime/image creation matters because every data-plane worker must carry known agents, security settings, telemetry, and rollback behavior.
8. Maintenance is architecture: onboarding, runbooks, expected failure modes, metrics, logs, debugging paths, and churn control must be represented as durable artifacts.

## Orvo translation

### 1. Self-service broker

Orvo should expose internal APIs/commands for provisioning:

- business/workspace/project;
- connector instance;
- metric/event definitions;
- workflow scheme;
- automation rule;
- SLA policy;
- operator surface projection;
- playbook/template.

Each request should create an auditable record and compile to runtime-safe specs. The broker does not need to implement the full Open Service Broker spec in the near term. For Orvo, the useful primitive is: request → validation → durable status/audit record → compiled runtime spec update.

### 2. Compiled runtime specs

Before a run, Orvo compiles a `CompiledBusinessRuntime` from:

- tenant/business config;
- connector registry entries;
- metric/event registry;
- workflow/case policies;
- delivery/surface policy;
- secret references;
- permission/rate-limit policy.

The runtime/data plane executes the compiled spec and records outcomes. It must not silently mutate source-of-truth configuration during execution. Video lesson: expose simple product parameters to operators/developers, then validate and compile them into richer runtime specs; do not expose the full internal runtime/config surface as user-editable input.

### 3. Gateway concerns

Centralize these instead of scattering them through adapters:

- tenant routing;
- authentication;
- RBAC/permission schemes;
- rate limits and quotas;
- idempotency keys;
- audit events;
- redaction;
- structured logs/traces;
- connector health and degraded-state classification.

### 4. Rate-limit service pattern

Steward-style config-driven rate limits map to Orvo as:

- per-tenant automation limits;
- per-connector API budgets;
- per-surface notification quotas;
- per-operator mutation throttles;
- safe retry/backoff policy;
- deterministic tests for quota exceeded / retry later / degraded state.

### 5. Extension/plugin model

Sovereign's template/data-source/plugin approach maps to Orvo as:

- connector registry with capabilities/scopes;
- workflow action registry;
- projection/surface renderer registry;
- playbook/template registry;
- custom field and issue type definitions;
- app/connector certification tests.

### 6. Observability and provenance

Every runtime and automation action should answer:

- which compiled spec ran;
- which connector calls succeeded/failed/degraded;
- which metrics/events/evidence were emitted;
- which cases were opened/updated/reopened;
- which rules fired and whether actions were dry-run/approved/executed;
- which messages/API responses were dispatched;
- which tokens/secrets were used only by reference and never leaked.

## Tooling recommendations

Short term, stay inside the current Python repo and add product-shaped contracts before infra:

- Pydantic models for specs and manifests;
- a small provisioning/status ledger for config-changing requests before introducing external queues;
- SQLite-backed ledger/audit tables;
- pytest contract tests;
- docs/specs/ADRs;
- external git worktrees and review manifests;
- structured JSON logs where useful.

Medium term, introduce platform-grade components only when they solve a concrete bottleneck:

- OpenTelemetry-compatible trace/log IDs;
- Prometheus-style metrics export;
- service/component catalog inspired by Compass;
- gateway middleware for auth/rate-limit/idempotency;
- SBOM/vulnerability/provenance checks before production deployments.

Long term, if Orvo becomes multi-service/multi-tenant enough:

- a real broker API;
- separate control-plane service;
- data-plane workers;
- service mesh/gateway technology;
- marketplace/app runtime;
- centralized observability stack.

## What not to do

- Do not install Envoy/xDS/Keycloak/Prometheus/Loki/Tempo/SaltStack just to look like Atlassian.
- Do not implement the full Open Service Broker API unless Orvo actually needs ecosystem-compatible provisioning.
- Do not introduce SQS/DynamoDB/CloudFormation/Packer/Envoy sidecars as first-class dependencies; translate their roles into current Python contracts, ledgers, tests, and docs first.
- Do not rewrite the existing deterministic report path; wrap it behind compiled runtime contracts.
- Do not let connector adapters become product logic.
- Do not let cron workers create more cron workers.

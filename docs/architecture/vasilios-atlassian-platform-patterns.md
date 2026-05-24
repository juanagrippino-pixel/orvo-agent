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

Use this as platform pattern input, not as a claim that every listed component is currently or officially used inside Atlassian.

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

Each request should create an auditable record and compile to runtime-safe specs.

### 2. Compiled runtime specs

Before a run, Orvo compiles a `CompiledBusinessRuntime` from:

- tenant/business config;
- connector registry entries;
- metric/event registry;
- workflow/case policies;
- delivery/surface policy;
- secret references;
- permission/rate-limit policy.

The runtime/data plane executes the compiled spec and records outcomes. It must not silently mutate source-of-truth configuration during execution.

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
- Do not rewrite the existing deterministic report path; wrap it behind compiled runtime contracts.
- Do not let connector adapters become product logic.
- Do not let cron workers create more cron workers.

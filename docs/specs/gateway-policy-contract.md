# Gateway Policy Contract

Status: Draft implementation contract  
Date: 2026-05-31  
Related: `docs/organization/orvo-operating-toolchain-blueprint.md`, `docs/architecture/vasilios-atlassian-platform-patterns.md`, `docs/specs/service-catalog-contract.md`

## Purpose

The gateway policy contract is Orvo's lightweight Python-runtime translation of shared edge concerns. It gives internal API/runtime routes one deterministic place to describe and evaluate:

- route identity and method;
- authenticated actor context;
- business scope;
- required permissions;
- rate-limit bucket metadata;
- idempotency requirements for mutations;
- audit event names and safe provenance fields.

This is intentionally **not** Envoy, Keycloak, Redis, or a new network gateway. It is an in-process contract in `app.brain.gateway_policy` that can later back middleware, broker APIs, or external edge infrastructure if the current Python runtime proves the need.

## Non-negotiable rules

1. Route handlers remain thin; business logic stays in services/stores.
2. Gateway policy manifests are metadata only and must never contain bearer values, raw tokens, OAuth material, connector credentials, or environment variables.
3. Mutating routes that can create side effects must declare `idempotency_required=true` before being exposed as automated/operator actions.
4. Business scope is evaluated from the authenticated principal, not from caller-supplied prose.
5. Permission checks are allowlisted by route policy; wildcard grants are for tests/admin bootstrap only.
6. Rate-limit keys are deterministic and safe to log after boundary redaction: `<bucket>:<business_id>:<redacted_actor_id>`.
7. Audit events record decision codes and whether an idempotency key was present, but not the idempotency key value itself. Actor identifiers are passed through the shared redaction helper before projection.

## Current schema

`GatewayRoutePolicy` fields:

| Field | Purpose |
| --- | --- |
| `route_key` | Stable route-family identifier, e.g. `operator_api.case_action.mutate`. |
| `method` | HTTP method the policy expects. |
| `path_template` | Human-readable route template for docs/review. |
| `surface` | Runtime surface (`operator_api` or `runtime`). |
| `required_permissions` | Permission keys the authenticated principal must hold. |
| `rate_limit` | Bucket, per-minute budget, and burst metadata. |
| `idempotency_required` | Whether requests must carry an idempotency key before execution. |
| `audit_event_type` | Stable audit/provenance event name emitted by policy decisions. |

`GatewayRequestContext` carries only request facts needed for evaluation: route key, method, business ID, optional authenticated principal, and optional idempotency key. `GatewayPolicyDecision` returns a safe decision envelope with status code, decision code, rate-limit key, idempotency requirement, and audit event metadata.

## Initial route policies

The first registry covers high-value internal boundaries without broad routing rewrites:

1. `operator_api.case_queue.read` — read-only case queue access; requires `cases:read`; no idempotency key.
2. `operator_api.case_action.mutate` — case lifecycle/comment/assignment actions; requires `cases:write`; idempotency key required.
3. `runtime.force_run.mutate` — operator-triggered runtime execution; requires `runtime:execute`; idempotency key required.

These are conventions and contract tests first. Existing Flask handlers can be wired to them in a later slice without changing the public response envelope.

## Decision codes

| Code | Status | Meaning |
| --- | ---: | --- |
| `allowed` | 200 | Principal, scope, permissions, method, and idempotency requirements passed. |
| `method_not_allowed` | 405 | Route key exists but method does not match policy. |
| `unauthenticated` | 401 | Authenticated principal is missing. |
| `business_scope_forbidden` | 403 | Principal is not allowed for the requested business. |
| `permission_denied` | 403 | Principal lacks one or more required route permissions. |
| `missing_idempotency_key` | 428 | Mutating route requires an idempotency key before execution. |

## Acceptance tests

Required tests live in `tests/contracts/test_gateway_policy_contract.py` and prove:

- the default registry covers the current internal boundaries in stable order;
- public manifests are deterministic and secret-safe;
- policy evaluation rejects missing auth, cross-business access, missing permissions, and missing idempotency keys;
- allowed decisions emit stable audit metadata and redacted rate-limit keys;
- actor identifiers are redacted before decision envelopes can be projected into logs, ledgers, or API diagnostics;
- duplicate route keys and unknown route lookups are rejected.

## Next extensions

- Wire `_with_internal_stores`/internal operator routes through `GatewayPolicyRegistry.evaluate` while preserving current response envelopes.
- Persist denied/allowed gateway decisions into the audit/run ledger once the Trust/Admin branch supplies a canonical audit store.
- Add per-route certification fixtures for connector provisioning and broker operations before adding new external infrastructure.

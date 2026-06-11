# Service Catalog Contract

Status: Draft implementation contract
Date: 2026-05-31
Related: `docs/organization/orvo-operating-toolchain-blueprint.md`, `docs/architecture/vasilios-atlassian-platform-patterns.md`

## Purpose

The service catalog is Orvo's lightweight Python-runtime translation of a Compass-style component catalog. It gives the control plane one typed place to answer:

- which component owns a runtime/control-plane concern;
- which module is the source of truth;
- which docs and tests prove the contract;
- which operational runbooks explain safe inspection and response paths;
- which runtime surfaces and observability signals a component participates in;
- which components depend on each other.

It is intentionally not a new infrastructure service. The first slice is an in-repo typed catalog in `app.brain.service_catalog`, backed by contract tests. External catalogs, dashboards, or metrics stacks can be added only after this contract earns its keep inside the current Python runtime.

## Non-negotiable rules

1. The catalog is descriptive metadata, not a new execution path.
2. It must not store credentials, tenant-specific values, environment variables, OAuth material, or raw connector parameters.
3. Component IDs are stable and unique.
4. Dependencies must reference known component IDs.
5. Public manifests must be deterministic and safe to project into docs or internal APIs.
6. The catalog points at existing source-of-truth modules; it must not duplicate business logic from runtime, connector, metric, case, API, or dispatch services.

## Current schema

`ServiceComponent` fields:

| Field | Purpose |
| --- | --- |
| `component_id` | Stable machine key for the component. |
| `display_name` | Human-readable component name. |
| `owner_department` | Autonomous department accountable for changes. |
| `source_of_truth` | Canonical Python module or package. |
| `status` | `active`, `draft`, or `planned`. |
| `tier` | `control_plane`, `runtime`, `surface`, or `platform`. |
| `docs` | Durable docs/specs that explain the component. |
| `code_paths` | Source paths reviewers should inspect. |
| `test_paths` | Tests that protect the component. |
| `runbooks` | Operational docs for safe inspection, degraded-state handling, and escalation. |
| `dependencies` | Other catalog component IDs required by this component. |
| `runtime_surfaces` | Runtime/API surfaces touched by the component. |
| `observability_signals` | Stable log/ledger/API field names useful for provenance. Signal names that reference actors, keys, or external identifiers must describe redacted/projected values, never raw credential-bearing values. |

## Certification schema

`certify_service_catalog(catalog, repo_root=...)` emits
`2026-06-11.service-catalog-certification.v1`, a deterministic developer-platform
quality gate for catalog metadata. It is intentionally metadata-only: it does not
import component modules or execute runtime code.

The certification report checks:

- every declared `docs`, `code_paths`, `test_paths`, and `runbooks` entry points
  at an existing repository file or directory;
- scalar metadata such as `display_name`, `owner_department`, and
  `source_of_truth` is safe for projection and does not contain secret-shaped
  material;
- list metadata such as paths, dependencies, runtime surfaces, and observability
  signals is also secret-safe;
- findings are safe envelopes with `component_id`, `field`, `code`, and message
  values that do not echo the unsafe raw text.

## Current components

The initial catalog covers the current Orvo Brain control-plane spine:

1. `compiled_runtime` — immutable runtime artifact and hash boundary.
2. `connector_registry` — connector capability, execution, health, rate-limit, and metric-family metadata.
3. `metric_registry` — semantic source of truth for metrics and evidence validation.
4. `run_ledger` — runtime execution provenance and status.
5. `operational_cases` — WorkItem/OperationalCase lifecycle source of truth.
6. `operator_api` — internal operator API projection layer.
7. `gateway_policy` — shared auth, permission, rate-limit, idempotency, request/trace provenance, schema-versioned gateway telemetry, and audit-decision conventions for internal edges. Its catalog entry points at `docs/operability/gateway-policy-telemetry-runbook.md` so operators and reviewers can inspect policy decisions without exposing raw idempotency keys or credentials.
8. `connector_provisioning` — side-effect-free self-service connector provisioning validation that reuses the connector registry, enforces `secret://` references, emits stable `operation_ref` correlation IDs plus redacted telemetry `provenance_ref` values, and emits redacted plans for developer/operator surfaces.
9. `delivery_dispatch` — dispatch/idempotency boundary for report and owner brief delivery.
10. `edge_developer_platform` — in-repo platform conventions and catalog contract.

## Acceptance tests

Required tests live in `tests/contracts/test_service_catalog_contract.py` and prove:

- default catalog coverage for core control-plane components;
- gateway policy ownership, source-of-truth metadata, and telemetry/provenance observability signals;
- connector provisioning ownership, source-of-truth metadata, docs, tests, dependencies, and telemetry/provenance observability signals;
- gateway policy runbook metadata is included in the public manifest and points at durable docs;
- service catalog certification accepts the default catalog's existing paths and
  flags missing paths plus secret-shaped metadata without echoing raw values;
- stable public manifest schema and component ordering;
- duplicate component IDs are rejected;
- dependencies must point at known components;
- owner and runtime-surface queries are deterministic;
- public manifest content is safe for projection and does not include credential material.

The read-only internal HTTP projection lives at `GET /internal/brain/businesses/{business_id}/service-catalog` and is covered by `tests/test_internal_operator_api.py`. The route must keep the standard internal envelope, require internal authentication plus `internal:read`, enforce `operator_api.service_catalog.read` in the gateway policy registry before projecting the manifest, and return only the deterministic public manifest from `app.brain.service_catalog`.

## Next extensions

Future slices can build on this contract without adding heavy infrastructure:

- add component-detail filtering once the read-only service catalog endpoint needs focused developer views;
- attach SLO/runbook links once SRE conventions land;
- add connector certification records under the same component/dependency model;
- join run-ledger events to catalog component IDs for provenance reports.
